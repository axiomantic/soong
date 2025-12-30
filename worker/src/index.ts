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

// KV namespace to track consecutive failures across cron runs
// Note: This would require adding KV binding in wrangler.toml for production
// For now, we'll use a global in-memory store (resets on each deployment)
let failureTracker: FailureTracker = {};

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
    const response = await fetch('https://cloud.lambdalabs.com/api/v1/instances', {
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
      'https://cloud.lambdalabs.com/api/v1/instance-operations/terminate',
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
    // Allow manual triggering via HTTP for testing
    if (request.method === 'GET' && new URL(request.url).pathname === '/trigger') {
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
    if (request.method === 'GET' && new URL(request.url).pathname === '/status') {
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

    return new Response('GPU Watchdog Worker\n\nEndpoints:\n- GET /trigger (manual run)\n- GET /status (view tracker)', {
      headers: {
        'Content-Type': 'text/plain',
      },
    });
  },
};
