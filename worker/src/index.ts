/**
 * GPU Watchdog - Cloudflare Worker
 *
 * Monitors Lambda GPU instances with "coding-stack" filesystem and terminates
 * instances that fail health checks for 2 consecutive checks (1 hour).
 *
 * Runs every 30 minutes via cron trigger.
 */

interface Env {
  LAMBDA_API_KEY: string;
  STATUS_DAEMON_TOKEN: string;
  KV?: KVNamespace;  // Optional KV namespace for history storage
}

interface LambdaInstance {
  id: string;
  name: string | null;
  ip: string | null;
  status: string;
  instance_type: {
    name: string;
    description: string;
    price_cents_per_hour: number;
  };
  region: {
    name: string;
    description: string;
  };
  ssh_key_names: string[];
  file_system_names: string[];
  created_at: string;
}

interface StatusResponse {
  instance_id: string;
  status: string;
  uptime_minutes: number;
  idle_minutes: number;
  shutdown_at: string;
  shutdown_in_minutes: number;
  model_loaded: string;
  gpu_utilization: number;
  boot_time: string;
}

interface FailureTracker {
  [instanceId: string]: number;
}

interface HistoryEvent {
  timestamp: string;
  instance_id: string;
  event_type: string;
  reason: string;
  uptime_minutes: number;
  gpu_type: string;
  region: string;
}

interface InstanceEvent {
  event_type: "launch" | "terminate" | "extend" | "idle_shutdown" | "watchdog_termination";
  timestamp: string;
  instance_id: string;
  instance_name: string;
  gpu_type: string;
  region: string;
  duration_minutes: number | null;
  cost_dollars: number | null;
  shutdown_reason: string | null;
  metrics: {
    tokens_generated: number | null;
    idle_percentage: number | null;
    lease_extensions: number;
    cpu_hours: number | null;
  } | null;
}

// KV namespace to track consecutive failures across cron runs
// Note: This would require adding KV binding in wrangler.toml for production
// For now, we'll use a global in-memory store (resets on each deployment)
let failureTracker: FailureTracker = {};

/**
 * Log a history event to KV storage
 * Note: Requires KV namespace binding configured in wrangler.toml
 */
async function logHistoryEvent(
  env: Env,
  instance: LambdaInstance,
  reason: string,
  uptimeMinutes: number
): Promise<void> {
  if (!env.KV) {
    console.log('KV namespace not configured, skipping history logging');
    return;
  }

  const timestamp = new Date().toISOString();

  const event: InstanceEvent = {
    event_type: 'watchdog_termination',
    timestamp,
    instance_id: instance.id,
    instance_name: instance.name || 'unnamed',
    gpu_type: instance.instance_type.name,
    region: instance.region.name,
    duration_minutes: uptimeMinutes,
    cost_dollars: null,
    shutdown_reason: reason,
    metrics: null,
  };

  // NEW KEY FORMAT: events/{timestamp}_{instance_id}_{event_type}
  const key = `events/${timestamp}_${instance.id}_watchdog_termination`;
  await env.KV.put(key, JSON.stringify(event), {
    expirationTtl: 90 * 24 * 60 * 60,  // 90 days
  });

  console.log(`Logged history event: ${key}`);
}

/**
 * Retry a function with exponential backoff
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  maxAttempts: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      if (attempt === maxAttempts) {
        break;
      }

      const delay = baseDelay * Math.pow(2, attempt - 1);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError;
}

/**
 * List all Lambda instances
 */
async function listInstances(apiKey: string): Promise<LambdaInstance[]> {
  return withRetry(async () => {
    const response = await fetch('https://cloud.lambda.ai/api/v1/instances', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Lambda API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json() as { data: LambdaInstance[] };
    return data.data || [];
  });
}

/**
 * Check instance health via status daemon
 */
async function checkInstanceHealth(
  instanceIp: string,
  statusToken: string
): Promise<StatusResponse | null> {
  return withRetry(async () => {
    const response = await fetch(`http://${instanceIp}:8080/status`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${statusToken}`,
      },
      signal: AbortSignal.timeout(10000), // 10 second timeout
    });

    if (!response.ok) {
      return null;
    }

    return await response.json() as StatusResponse;
  }, 3, 1000).catch(() => null); // Return null on all failures
}

/**
 * Terminate a Lambda instance
 */
async function terminateInstance(
  apiKey: string,
  instanceId: string
): Promise<void> {
  return withRetry(async () => {
    const response = await fetch(
      'https://cloud.lambda.ai/api/v1/instance-operations/terminate',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          instance_ids: [instanceId],
        }),
      }
    );

    if (!response.ok) {
      throw new Error(`Terminate failed: ${response.status} ${response.statusText}`);
    }
  });
}

/**
 * Main watchdog logic
 */
async function watchdogCheck(env: Env): Promise<string[]> {
  const logs: string[] = [];

  logs.push(`[${new Date().toISOString()}] Watchdog check starting`);

  try {
    // Fetch all instances
    const instances = await listInstances(env.LAMBDA_API_KEY);
    logs.push(`Found ${instances.length} total instances`);

    // Filter to instances with "coding-stack" filesystem
    const codingStackInstances = instances.filter(instance =>
      instance.file_system_names?.includes('coding-stack')
    );
    logs.push(`Found ${codingStackInstances.length} instances with coding-stack filesystem`);

    // Check each instance
    for (const instance of codingStackInstances) {
      if (!instance.ip) {
        logs.push(`Instance ${instance.id} has no IP yet (still booting?), skipping`);
        continue;
      }

      logs.push(`Checking instance ${instance.id} (${instance.ip})`);

      // Attempt health check
      const health = await checkInstanceHealth(instance.ip, env.STATUS_DAEMON_TOKEN);

      if (health && health.status === 'healthy') {
        // Health check passed - reset failure count
        if (failureTracker[instance.id]) {
          logs.push(`Instance ${instance.id} recovered (was ${failureTracker[instance.id]} failures)`);
          delete failureTracker[instance.id];
        } else {
          logs.push(`Instance ${instance.id} healthy (uptime: ${health.uptime_minutes}m, idle: ${health.idle_minutes}m)`);
        }
      } else {
        // Health check failed - increment failure count
        const previousFailures = failureTracker[instance.id] || 0;
        const currentFailures = previousFailures + 1;
        failureTracker[instance.id] = currentFailures;

        logs.push(`Instance ${instance.id} health check failed (${currentFailures} consecutive failures)`);

        // Terminate after 2 consecutive failures (2 checks * 30 min = 1 hour)
        if (currentFailures >= 2) {
          logs.push(`Instance ${instance.id} failed ${currentFailures} consecutive checks, terminating...`);

          try {
            // Calculate uptime (rough estimate based on created_at)
            const createdAt = new Date(instance.created_at);
            const now = new Date();
            const uptimeMinutes = Math.floor((now.getTime() - createdAt.getTime()) / (1000 * 60));

            // Log history event before terminating
            await logHistoryEvent(
              env,
              instance,
              'watchdog: health check failures',
              uptimeMinutes
            );

            await terminateInstance(env.LAMBDA_API_KEY, instance.id);
            logs.push(`Instance ${instance.id} terminated successfully`);
            delete failureTracker[instance.id];
          } catch (error) {
            const errorMsg = error instanceof Error ? error.message : String(error);
            logs.push(`Failed to terminate instance ${instance.id}: ${errorMsg}`);
          }
        }
      }
    }

    // Clean up stale failure tracker entries (instances that no longer exist)
    const currentInstanceIds = new Set(codingStackInstances.map(i => i.id));
    for (const trackedId in failureTracker) {
      if (!currentInstanceIds.has(trackedId)) {
        logs.push(`Removing stale tracker entry for ${trackedId}`);
        delete failureTracker[trackedId];
      }
    }

  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    logs.push(`ERROR: ${errorMsg}`);
  }

  logs.push(`[${new Date().toISOString()}] Watchdog check complete`);
  return logs;
}

/**
 * Cloudflare Worker entry point
 */
export default {
  async scheduled(
    event: ScheduledEvent,
    env: Env,
    ctx: ExecutionContext
  ): Promise<void> {
    // Run watchdog check
    const logs = await watchdogCheck(env);

    // Log all output
    console.log(logs.join('\n'));
  },

  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext
  ): Promise<Response> {
    const url = new URL(request.url);

    // Health endpoint for deployment verification
    if (request.method === 'GET' && url.pathname === '/health') {
      return new Response(
        JSON.stringify({
          status: 'healthy',
          service: 'gpu-watchdog',
          version: '2.0.0',
          kv_available: !!env.KV,
          timestamp: new Date().toISOString(),
        }),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    // Allow manual triggering via HTTP for testing
    if (request.method === 'GET' && url.pathname === '/trigger') {
      const logs = await watchdogCheck(env);

      return new Response(
        JSON.stringify({
          success: true,
          logs,
          timestamp: new Date().toISOString(),
        }),
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    // Status endpoint
    if (request.method === 'GET' && url.pathname === '/status') {
      return new Response(
        JSON.stringify({
          service: 'gpu-watchdog',
          version: '1.0.0',
          tracked_failures: failureTracker,
          timestamp: new Date().toISOString(),
        }),
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    // History endpoint - returns recent termination events
    if (request.method === 'GET' && url.pathname === '/history') {
      if (!env.KV) {
        return new Response(
          JSON.stringify({
            error: 'KV namespace not configured',
            events: [],
          }),
          {
            status: 503,
            headers: {
              'Content-Type': 'application/json',
            },
          }
        );
      }

      try {
        // Get hours parameter (default 24)
        const hours = parseInt(url.searchParams.get('hours') || '24', 10);
        const cutoffTime = new Date(Date.now() - hours * 60 * 60 * 1000);

        // List all history keys
        const { keys } = await env.KV.list({ prefix: 'history:' });

        // Fetch and filter events
        const events: HistoryEvent[] = [];
        for (const key of keys) {
          const value = await env.KV.get(key.name);
          if (value) {
            const event: HistoryEvent = JSON.parse(value);
            const eventTime = new Date(event.timestamp);
            if (eventTime > cutoffTime) {
              events.push(event);
            }
          }
        }

        // Sort by timestamp descending (newest first)
        events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

        return new Response(
          JSON.stringify({
            events,
            count: events.length,
            hours,
            timestamp: new Date().toISOString(),
          }),
          {
            headers: {
              'Content-Type': 'application/json',
            },
          }
        );
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return new Response(
          JSON.stringify({
            error: errorMsg,
            events: [],
          }),
          {
            status: 500,
            headers: {
              'Content-Type': 'application/json',
            },
          }
        );
      }
    }

    // POST /event - Log instance lifecycle events
    if (request.method === 'POST' && url.pathname === '/event') {
      // Verify auth
      const authHeader = request.headers.get('Authorization');
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return new Response(
          JSON.stringify({ error: 'Missing authorization header' }),
          { status: 401, headers: { 'Content-Type': 'application/json' } }
        );
      }

      const token = authHeader.substring(7);
      if (token !== env.STATUS_DAEMON_TOKEN) {
        return new Response(
          JSON.stringify({ error: 'Invalid authorization token' }),
          { status: 401, headers: { 'Content-Type': 'application/json' } }
        );
      }

      // Validate KV availability
      if (!env.KV) {
        return new Response(
          JSON.stringify({ error: 'KV namespace not configured' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
      }

      try {
        // Parse request body
        const event: InstanceEvent = await request.json();

        // Validate required fields
        if (!event.event_type || !event.timestamp || !event.instance_id) {
          return new Response(
            JSON.stringify({ error: 'Missing required fields: event_type, timestamp, instance_id' }),
            { status: 400, headers: { 'Content-Type': 'application/json' } }
          );
        }

        // Build KV key: events/{ISO8601_timestamp}_{instance_id}_{event_type}
        const key = `events/${event.timestamp}_${event.instance_id}_${event.event_type}`;

        // Write to KV with 90-day TTL
        await env.KV.put(key, JSON.stringify(event), {
          expirationTtl: 90 * 24 * 60 * 60,  // 90 days in seconds
        });

        return new Response(
          JSON.stringify({
            success: true,
            key,
            timestamp: event.timestamp,
          }),
          { status: 201, headers: { 'Content-Type': 'application/json' } }
        );
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return new Response(
          JSON.stringify({ error: `KV write failed: ${errorMsg}` }),
          { status: 500, headers: { 'Content-Type': 'application/json' } }
        );
      }
    }

    // GET /events - Query instance lifecycle events
    if (request.method === 'GET' && url.pathname === '/events') {
      if (!env.KV) {
        return new Response(
          JSON.stringify({ error: 'KV namespace not configured', events: [] }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
      }

      try {
        // Parse query parameters
        const hours = parseInt(url.searchParams.get('hours') || '24', 10);
        const instanceId = url.searchParams.get('instance_id');
        const eventType = url.searchParams.get('event_type');
        const limit = parseInt(url.searchParams.get('limit') || '100', 10);

        // Calculate cutoff time
        const cutoffTime = new Date(Date.now() - hours * 60 * 60 * 1000);

        // List all event keys
        const { keys } = await env.KV.list({ prefix: 'events/' });

        // Fetch and filter events
        const events: InstanceEvent[] = [];
        for (const key of keys) {
          if (events.length >= limit) break;

          const value = await env.KV.get(key.name);
          if (!value) continue;

          const event: InstanceEvent = JSON.parse(value);
          const eventTime = new Date(event.timestamp);

          // Apply filters
          if (eventTime <= cutoffTime) continue;
          if (instanceId && event.instance_id !== instanceId) continue;
          if (eventType && event.event_type !== eventType) continue;

          events.push(event);
        }

        // Sort by timestamp descending (newest first)
        events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

        // Calculate aggregates
        let totalHours = 0;
        let totalCost = 0;
        for (const event of events) {
          if (event.duration_minutes !== null) {
            totalHours += event.duration_minutes / 60;
          }
          if (event.cost_dollars !== null) {
            totalCost += event.cost_dollars;
          }
        }

        return new Response(
          JSON.stringify({
            events,
            count: events.length,
            total_hours: parseFloat(totalHours.toFixed(2)),
            total_cost: parseFloat(totalCost.toFixed(2)),
            query: { hours, instance_id: instanceId, event_type: eventType, limit },
            timestamp: new Date().toISOString(),
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return new Response(
          JSON.stringify({ error: errorMsg, events: [] }),
          { status: 500, headers: { 'Content-Type': 'application/json' } }
        );
      }
    }

    return new Response('GPU Watchdog Worker\n\nEndpoints:\n- GET /health (health check)\n- GET /trigger (manual run)\n- GET /status (view tracker)\n- GET /history?hours=24 (legacy termination history)\n- POST /event (log lifecycle event, auth required)\n- GET /events?hours=24&instance_id=X&event_type=Y&limit=100 (query events)', {
      headers: {
        'Content-Type': 'text/plain',
      },
    });
  },
};
