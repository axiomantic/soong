/**
 * Worker Tests - Heartbeat-based Watchdog
 *
 * These tests verify the actual behavior of the heartbeat system by
 * calling the worker's fetch handler directly with mocked environments.
 *
 * Test categories:
 * 1. POST /heartbeat - stores heartbeats correctly
 * 2. GET /heartbeats - returns stored heartbeats
 * 3. Authentication enforcement
 * 4. Error handling
 * 5. Integration lifecycle tests
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import worker from "./index";

// Test constants
const STATUS_TOKEN = "test-status-token-12345";
const LAMBDA_API_KEY = "test-lambda-api-key";

// Helper to create authenticated request
function createAuthRequest(
  method: string,
  path: string,
  body?: object
): Request {
  const options: RequestInit = {
    method,
    headers: {
      Authorization: `Bearer ${STATUS_TOKEN}`,
      "Content-Type": "application/json",
    },
  };
  if (body) {
    options.body = JSON.stringify(body);
  }
  return new Request(`http://localhost${path}`, options);
}

// Helper to create unauthenticated request
function createRequest(method: string, path: string, body?: object): Request {
  const options: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) {
    options.body = JSON.stringify(body);
  }
  return new Request(`http://localhost${path}`, options);
}

// Mock KV namespace that stores data in memory
function createMockKV(): KVNamespace {
  const store = new Map<string, string>();

  return {
    get: vi.fn(async (key: string) => store.get(key) ?? null),
    put: vi.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    delete: vi.fn(async (key: string) => {
      store.delete(key);
    }),
    list: vi.fn(async (options?: { prefix?: string }) => {
      const keys: { name: string }[] = [];
      for (const key of store.keys()) {
        if (!options?.prefix || key.startsWith(options.prefix)) {
          keys.push({ name: key });
        }
      }
      return { keys, list_complete: true, cursor: "" };
    }),
    getWithMetadata: vi.fn(async (key: string) => ({
      value: store.get(key) ?? null,
      metadata: null,
    })),
  } as unknown as KVNamespace;
}

// Create test env with mocked KV
function createTestEnv(kv?: KVNamespace | null) {
  return {
    LAMBDA_API_KEY,
    STATUS_DAEMON_TOKEN: STATUS_TOKEN,
    KV: kv === null ? undefined : (kv ?? createMockKV()),
  };
}

// Create mock execution context
function createMockCtx() {
  return {
    waitUntil: vi.fn(),
    passThroughOnException: vi.fn(),
  } as unknown as ExecutionContext;
}

describe("POST /heartbeat", () => {
  it("stores heartbeat with correct key format", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    const payload = {
      instance_id: "test-instance-123",
      timestamp: "2024-01-15T10:30:00.000Z",
      uptime_minutes: 45,
      model_loaded: "deepseek-r1-70b",
      sglang_healthy: true,
      n8n_healthy: true,
    };

    const request = createAuthRequest("POST", "/heartbeat", payload);
    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(200);

    const body = (await response.json()) as { success: boolean; key: string };
    expect(body.success).toBe(true);
    expect(body.key).toBe("heartbeats/test-instance-123");

    // Verify KV was called with correct key
    expect(mockKV.put).toHaveBeenCalledWith(
      "heartbeats/test-instance-123",
      expect.any(String),
      expect.objectContaining({ expirationTtl: 600 })
    );
  });

  it("stores heartbeat with received_at timestamp", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    const payload = {
      instance_id: "test-instance-456",
      timestamp: "2024-01-15T10:30:00.000Z",
      uptime_minutes: 30,
      model_loaded: "test-model",
      sglang_healthy: true,
      n8n_healthy: false,
    };

    const request = createAuthRequest("POST", "/heartbeat", payload);
    await worker.fetch(request, testEnv, ctx);

    // Get the stored value from the mock
    const putCalls = (mockKV.put as ReturnType<typeof vi.fn>).mock.calls;
    expect(putCalls.length).toBe(1);

    const storedValue = JSON.parse(putCalls[0][1]);
    expect(storedValue.instance_id).toBe("test-instance-456");
    expect(storedValue.sglang_healthy).toBe(true);
    expect(storedValue.n8n_healthy).toBe(false);
    expect(storedValue.received_at).toBeDefined();
    // received_at should be a valid ISO timestamp
    expect(new Date(storedValue.received_at).toISOString()).toBe(
      storedValue.received_at
    );
  });

  it("returns 401 without authorization header", async () => {
    const testEnv = createTestEnv();
    const ctx = createMockCtx();

    const request = createRequest("POST", "/heartbeat", {
      instance_id: "test-123",
      timestamp: "2024-01-15T10:30:00.000Z",
    });

    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(401);
    const body = (await response.json()) as { error: string };
    expect(body.error).toBe("unauthorized");
  });

  it("returns 401 with wrong token", async () => {
    const testEnv = createTestEnv();
    const ctx = createMockCtx();

    const request = new Request("http://localhost/heartbeat", {
      method: "POST",
      headers: {
        Authorization: "Bearer wrong-token",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        instance_id: "test-123",
        timestamp: "2024-01-15T10:30:00.000Z",
      }),
    });

    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(401);
  });

  it("returns 400 when instance_id is missing", async () => {
    const testEnv = createTestEnv();
    const ctx = createMockCtx();

    const request = createAuthRequest("POST", "/heartbeat", {
      timestamp: "2024-01-15T10:30:00.000Z",
      uptime_minutes: 30,
    });

    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: string };
    expect(body.error).toContain("instance_id");
  });

  it("returns 400 when timestamp is missing", async () => {
    const testEnv = createTestEnv();
    const ctx = createMockCtx();

    const request = createAuthRequest("POST", "/heartbeat", {
      instance_id: "test-123",
      uptime_minutes: 30,
    });

    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: string };
    expect(body.error).toContain("timestamp");
  });

  it("returns 503 when KV is not configured", async () => {
    const testEnv = createTestEnv(null);
    const ctx = createMockCtx();

    const request = createAuthRequest("POST", "/heartbeat", {
      instance_id: "test-123",
      timestamp: "2024-01-15T10:30:00.000Z",
    });

    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(503);
    const body = (await response.json()) as { error: string };
    expect(body.error).toContain("KV");
  });

  it("returns 400 for invalid JSON body", async () => {
    const testEnv = createTestEnv();
    const ctx = createMockCtx();

    const request = new Request("http://localhost/heartbeat", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${STATUS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: "not valid json",
    });

    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: string };
    expect(body.error).toBe("invalid JSON");
  });

  it("uses 10 minute TTL for heartbeat storage", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    const request = createAuthRequest("POST", "/heartbeat", {
      instance_id: "ttl-test",
      timestamp: "2024-01-15T10:30:00.000Z",
    });

    await worker.fetch(request, testEnv, ctx);

    // Verify TTL is 600 seconds (10 minutes)
    expect(mockKV.put).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(String),
      { expirationTtl: 600 }
    );
  });
});

describe("GET /heartbeats", () => {
  it("returns all stored heartbeats", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    // Pre-populate KV with heartbeats
    const heartbeat1 = {
      instance_id: "instance-1",
      timestamp: "2024-01-15T10:30:00.000Z",
      received_at: "2024-01-15T10:30:01.000Z",
      sglang_healthy: true,
      n8n_healthy: true,
    };
    const heartbeat2 = {
      instance_id: "instance-2",
      timestamp: "2024-01-15T10:31:00.000Z",
      received_at: "2024-01-15T10:31:01.000Z",
      sglang_healthy: false,
      n8n_healthy: true,
    };

    await mockKV.put("heartbeats/instance-1", JSON.stringify(heartbeat1));
    await mockKV.put("heartbeats/instance-2", JSON.stringify(heartbeat2));

    const request = createAuthRequest("GET", "/heartbeats");
    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      heartbeats: unknown[];
      count: number;
    };
    expect(body.count).toBe(2);
    expect(body.heartbeats).toHaveLength(2);
  });

  it("returns empty array when no heartbeats exist", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    const request = createAuthRequest("GET", "/heartbeats");
    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      heartbeats: unknown[];
      count: number;
    };
    expect(body.count).toBe(0);
    expect(body.heartbeats).toHaveLength(0);
  });

  it("returns 401 without authorization", async () => {
    const testEnv = createTestEnv();
    const ctx = createMockCtx();

    const request = createRequest("GET", "/heartbeats");
    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(401);
  });

  it("only returns heartbeats with 'heartbeats/' prefix", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    // Add heartbeat and non-heartbeat entries
    await mockKV.put(
      "heartbeats/instance-1",
      JSON.stringify({ instance_id: "instance-1" })
    );
    await mockKV.put(
      "events/some-event",
      JSON.stringify({ event_type: "launch" })
    );
    await mockKV.put("other/data", JSON.stringify({ foo: "bar" }));

    const request = createAuthRequest("GET", "/heartbeats");
    const response = await worker.fetch(request, testEnv, ctx);

    const body = (await response.json()) as {
      heartbeats: unknown[];
      count: number;
    };
    expect(body.count).toBe(1);
  });
});

describe("GET /status", () => {
  it("returns heartbeat count and version info", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    // Add some heartbeats
    await mockKV.put(
      "heartbeats/instance-1",
      JSON.stringify({ instance_id: "instance-1" })
    );
    await mockKV.put(
      "heartbeats/instance-2",
      JSON.stringify({ instance_id: "instance-2" })
    );

    const request = createRequest("GET", "/status");
    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      service: string;
      version: string;
      mode: string;
      active_heartbeats: number;
    };
    expect(body.service).toBe("gpu-watchdog");
    expect(body.version).toBe("3.0.0");
    expect(body.mode).toBe("heartbeat-based");
    expect(body.active_heartbeats).toBe(2);
  });

  it("does not require authentication", async () => {
    const testEnv = createTestEnv();
    const ctx = createMockCtx();

    const request = createRequest("GET", "/status");
    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(200);
  });
});

describe("GET /health", () => {
  it("returns healthy status with KV availability", async () => {
    const testEnv = createTestEnv();
    const ctx = createMockCtx();

    const request = createRequest("GET", "/health");
    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(200);
    const body = (await response.json()) as {
      status: string;
      kv_available: boolean;
      service: string;
    };
    expect(body.status).toBe("healthy");
    expect(body.kv_available).toBe(true);
    expect(body.service).toBe("gpu-watchdog");
  });

  it("reports kv_available false when KV not configured", async () => {
    const testEnv = createTestEnv(null);
    const ctx = createMockCtx();

    const request = createRequest("GET", "/health");
    const response = await worker.fetch(request, testEnv, ctx);

    expect(response.status).toBe(200);
    const body = (await response.json()) as { kv_available: boolean };
    expect(body.kv_available).toBe(false);
  });
});

describe("Heartbeat lifecycle integration", () => {
  it("heartbeat can be stored and retrieved", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    // 1. Store a heartbeat
    const storeRequest = createAuthRequest("POST", "/heartbeat", {
      instance_id: "lifecycle-test-instance",
      timestamp: "2024-01-15T10:30:00.000Z",
      uptime_minutes: 60,
      model_loaded: "test-model",
      sglang_healthy: true,
      n8n_healthy: false,
    });

    const storeResponse = await worker.fetch(storeRequest, testEnv, ctx);
    expect(storeResponse.status).toBe(200);

    // 2. Retrieve heartbeats
    const listRequest = createAuthRequest("GET", "/heartbeats");
    const listResponse = await worker.fetch(listRequest, testEnv, ctx);

    expect(listResponse.status).toBe(200);
    const body = (await listResponse.json()) as {
      heartbeats: Array<{
        instance_id: string;
        sglang_healthy: boolean;
        n8n_healthy: boolean;
        received_at: string;
      }>;
    };

    expect(body.heartbeats).toHaveLength(1);
    expect(body.heartbeats[0].instance_id).toBe("lifecycle-test-instance");
    expect(body.heartbeats[0].sglang_healthy).toBe(true);
    expect(body.heartbeats[0].n8n_healthy).toBe(false);
    expect(body.heartbeats[0].received_at).toBeDefined();
  });

  it("multiple heartbeats from same instance overwrite each other", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    // First heartbeat
    await worker.fetch(
      createAuthRequest("POST", "/heartbeat", {
        instance_id: "same-instance",
        timestamp: "2024-01-15T10:30:00.000Z",
        uptime_minutes: 30,
        model_loaded: "model-v1",
        sglang_healthy: true,
        n8n_healthy: true,
      }),
      testEnv,
      ctx
    );

    // Second heartbeat from same instance
    await worker.fetch(
      createAuthRequest("POST", "/heartbeat", {
        instance_id: "same-instance",
        timestamp: "2024-01-15T10:31:00.000Z",
        uptime_minutes: 31,
        model_loaded: "model-v1",
        sglang_healthy: false, // changed
        n8n_healthy: true,
      }),
      testEnv,
      ctx
    );

    // Should only have one heartbeat (latest)
    const listResponse = await worker.fetch(
      createAuthRequest("GET", "/heartbeats"),
      testEnv,
      ctx
    );

    const body = (await listResponse.json()) as {
      heartbeats: Array<{
        instance_id: string;
        sglang_healthy: boolean;
        uptime_minutes: number;
      }>;
    };

    expect(body.heartbeats).toHaveLength(1);
    expect(body.heartbeats[0].sglang_healthy).toBe(false); // Latest value
    expect(body.heartbeats[0].uptime_minutes).toBe(31); // Latest value
  });

  it("status endpoint reflects current heartbeat count", async () => {
    const mockKV = createMockKV();
    const testEnv = createTestEnv(mockKV);
    const ctx = createMockCtx();

    // Check initial status
    let statusResponse = await worker.fetch(
      createRequest("GET", "/status"),
      testEnv,
      ctx
    );
    let status = (await statusResponse.json()) as { active_heartbeats: number };
    expect(status.active_heartbeats).toBe(0);

    // Add heartbeats
    await worker.fetch(
      createAuthRequest("POST", "/heartbeat", {
        instance_id: "instance-a",
        timestamp: new Date().toISOString(),
      }),
      testEnv,
      ctx
    );
    await worker.fetch(
      createAuthRequest("POST", "/heartbeat", {
        instance_id: "instance-b",
        timestamp: new Date().toISOString(),
      }),
      testEnv,
      ctx
    );

    // Check updated status
    statusResponse = await worker.fetch(
      createRequest("GET", "/status"),
      testEnv,
      ctx
    );
    status = (await statusResponse.json()) as { active_heartbeats: number };
    expect(status.active_heartbeats).toBe(2);
  });
});

describe("Help text", () => {
  it("shows heartbeat endpoints in help text", async () => {
    const testEnv = createTestEnv();
    const ctx = createMockCtx();

    const request = createRequest("GET", "/");
    const response = await worker.fetch(request, testEnv, ctx);

    const body = await response.text();
    expect(body).toContain("POST /heartbeat");
    expect(body).toContain("GET /heartbeats");
    expect(body).toContain("Heartbeat-Based");
  });
});
