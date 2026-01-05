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

// StatusResponse and FailureTracker removed - no longer needed with heartbeat-based watchdog

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
  instance_name: string | null;
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

interface HeartbeatPayload {
  instance_id: string;
  timestamp: string;
  uptime_minutes: number;
  model_loaded: string;
  sglang_healthy: boolean;
  n8n_healthy: boolean;
  received_at?: string;
}

// Heartbeat-based watchdog: instances push heartbeats to Worker
// No inbound ports needed - fully push-based architecture

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
 * List all heartbeats from KV storage
 */
async function listHeartbeats(env: Env): Promise<HeartbeatPayload[]> {
  if (!env.KV) {
    return [];
  }

  const list = await env.KV.list({ prefix: 'heartbeats/' });
  const heartbeats: HeartbeatPayload[] = [];

  for (const key of list.keys) {
    const value = await env.KV.get(key.name);
    if (value) {
      try {
        heartbeats.push(JSON.parse(value) as HeartbeatPayload);
      } catch {
        console.warn(`Invalid heartbeat JSON for key ${key.name}`);
      }
    }
  }

  return heartbeats;
}

/**
 * Terminate a Lambda instance
 */
async function terminateInstance(
  env: Env,
  instanceId: string
): Promise<void> {
  return withRetry(async () => {
    const response = await fetch(
      'https://cloud.lambda.ai/api/v1/instance-operations/terminate',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.LAMBDA_API_KEY}`,
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
 * Log watchdog termination event to KV
 */
async function logWatchdogEvent(
  env: Env,
  instance: LambdaInstance,
  reason: string
): Promise<void> {
  if (!env.KV) return;

  const event: InstanceEvent = {
    event_type: 'watchdog_termination',
    timestamp: new Date().toISOString(),
    instance_id: instance.id,
    instance_name: instance.name,
    gpu_type: instance.instance_type?.name || 'unknown',
    region: instance.region?.name || 'unknown',
    duration_minutes: null,
    cost_dollars: null,
    shutdown_reason: reason,
    metrics: null,
  };

  const key = `events/${event.timestamp}_${instance.id}_watchdog`;
  await env.KV.put(key, JSON.stringify(event), { expirationTtl: 90 * 24 * 60 * 60 });
  console.log(`Logged watchdog event: ${key}`);
}

/**
 * Main watchdog logic - heartbeat-based detection
 *
 * Instances push heartbeats to Worker. This function:
 * 1. Lists running instances from Lambda API
 * 2. Compares against heartbeats in KV
 * 3. Terminates instances with stale/missing heartbeats
 */
async function watchdogCheck(env: Env): Promise<string[]> {
  const logs: string[] = [];
  const STALE_THRESHOLD_MS = 5 * 60 * 1000; // 5 minutes
  const GRACE_PERIOD_MS = 10 * 60 * 1000; // 10 minutes for new instances

  logs.push(`[${new Date().toISOString()}] Watchdog check starting (heartbeat-based)`);

  try {
    // 1. Get all running instances from Lambda API
    const instances = await listInstances(env.LAMBDA_API_KEY);
    logs.push(`Found ${instances.length} total instances`);

    // Filter to instances with "coding-stack" filesystem
    const codingStackInstances = instances.filter(instance =>
      instance.file_system_names?.includes('coding-stack')
    );
    logs.push(`Found ${codingStackInstances.length} instances with coding-stack filesystem`);

    if (codingStackInstances.length === 0) {
      logs.push('No instances to check');
      logs.push(`[${new Date().toISOString()}] Watchdog check complete`);
      return logs;
    }

    // 2. Get all heartbeats from KV
    const heartbeats = await listHeartbeats(env);
    const heartbeatMap = new Map(heartbeats.map(h => [h.instance_id, h]));
    logs.push(`Found ${heartbeats.length} heartbeats in KV`);

    // 3. Check each instance
    const now = Date.now();
    for (const instance of codingStackInstances) {
      const heartbeat = heartbeatMap.get(instance.id);
      const shortId = instance.id.slice(0, 8);

      if (!heartbeat) {
        // No heartbeat ever received - check if instance is new
        const createdAt = new Date(instance.created_at).getTime();
        const age = now - createdAt;

        if (age > GRACE_PERIOD_MS) {
          logs.push(`Instance ${shortId}: No heartbeat, age ${Math.round(age / 60000)}m - TERMINATING`);
          try {
            await terminateInstance(env, instance.id);
            await logWatchdogEvent(env, instance, 'no_heartbeat');
            logs.push(`Instance ${shortId}: Terminated successfully`);
          } catch (e) {
            const errorMsg = e instanceof Error ? e.message : String(e);
            logs.push(`Instance ${shortId}: ERROR terminating: ${errorMsg}`);
          }
        } else {
          logs.push(`Instance ${shortId}: No heartbeat, age ${Math.round(age / 60000)}m - grace period`);
        }
        continue;
      }

      // Has heartbeat - check staleness
      const lastSeen = new Date(heartbeat.received_at!).getTime();
      const staleness = now - lastSeen;

      if (staleness > STALE_THRESHOLD_MS) {
        logs.push(`Instance ${shortId}: Stale heartbeat (${Math.round(staleness / 60000)}m ago) - TERMINATING`);
        try {
          await terminateInstance(env, instance.id);
          await logWatchdogEvent(env, instance, 'stale_heartbeat');
          logs.push(`Instance ${shortId}: Terminated successfully`);
        } catch (e) {
          const errorMsg = e instanceof Error ? e.message : String(e);
          logs.push(`Instance ${shortId}: ERROR terminating: ${errorMsg}`);
        }
      } else {
        const healthInfo = heartbeat.sglang_healthy ? 'sglang:ok' : 'sglang:down';
        logs.push(`Instance ${shortId}: OK (${Math.round(staleness / 1000)}s ago, ${healthInfo})`);
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
      const heartbeats = await listHeartbeats(env);
      return new Response(
        JSON.stringify({
          service: 'gpu-watchdog',
          version: '3.0.0',
          mode: 'heartbeat-based',
          active_heartbeats: heartbeats.length,
          timestamp: new Date().toISOString(),
        }),
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
    }

    // POST /heartbeat - Receive heartbeat from instance
    if (request.method === 'POST' && url.pathname === '/heartbeat') {
      // Validate auth
      const authHeader = request.headers.get('Authorization') || '';
      const token = authHeader.replace('Bearer ', '');
      if (token !== env.STATUS_DAEMON_TOKEN) {
        return new Response(
          JSON.stringify({ error: 'unauthorized' }),
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

      let payload: HeartbeatPayload;
      try {
        payload = await request.json() as HeartbeatPayload;
      } catch {
        return new Response(
          JSON.stringify({ error: 'invalid JSON' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } }
        );
      }

      // Validate required fields
      if (!payload.instance_id || !payload.timestamp) {
        return new Response(
          JSON.stringify({ error: 'missing instance_id or timestamp' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } }
        );
      }

      // Store in KV with 10-minute TTL (2x stale threshold for buffer)
      const key = `heartbeats/${payload.instance_id}`;
      const value: HeartbeatPayload = {
        ...payload,
        received_at: new Date().toISOString(),
      };

      await env.KV.put(key, JSON.stringify(value), { expirationTtl: 600 });

      return new Response(
        JSON.stringify({ success: true, key }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // GET /heartbeats - List all current heartbeats (for debugging)
    if (request.method === 'GET' && url.pathname === '/heartbeats') {
      // Validate auth
      const authHeader = request.headers.get('Authorization') || '';
      const token = authHeader.replace('Bearer ', '');
      if (token !== env.STATUS_DAEMON_TOKEN) {
        return new Response(
          JSON.stringify({ error: 'unauthorized' }),
          { status: 401, headers: { 'Content-Type': 'application/json' } }
        );
      }

      const heartbeats = await listHeartbeats(env);
      return new Response(
        JSON.stringify({ heartbeats, count: heartbeats.length }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
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

    return new Response('GPU Watchdog Worker (Heartbeat-Based)\n\nEndpoints:\n- GET /health (health check)\n- GET /trigger (manual watchdog run)\n- GET /status (view active heartbeats)\n- POST /heartbeat (receive instance heartbeat, auth required)\n- GET /heartbeats (list all heartbeats, auth required)\n- POST /event (log lifecycle event, auth required)\n- GET /events?hours=24 (query events)\n- GET /history?hours=24 (legacy termination history)', {
      headers: {
        'Content-Type': 'text/plain',
      },
    });
  },
};
