/**
 * Centralized REST & Realtime (WebSocket / SSE) Client for Smart Parking FastAPI Backend.
 * Automatically adapts to localhost, LAN IP (192.168.x.x), or Public HTTPS Tunnel / Cloud URL
 * so external viewers never hit hardcoded 127.0.0.1 on their own device.
 */
import { RealtimeEnvelope } from "../shared/types";

const TOKEN_STORAGE_KEY = "pbl4_smart_parking_jwt_token";

function resolveApiBaseUrl(): string {
  const envUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, "");
  if (typeof window === "undefined") {
    return envUrl || "http://127.0.0.1:8000";
  }
  if (envUrl) return envUrl;
  const { protocol, hostname, port, origin } = window.location;
  return ["5173", "3000"].includes(port) ? `${protocol}//${hostname}:8000` : origin;
}

function resolveWsUrl(apiBase: string): string {
  const envWs = import.meta.env.VITE_WS_URL as string | undefined;
  return envWs || `${apiBase.replace(/^http/, "ws")}/api/ws`;
}

export const API_BASE_URL: string = resolveApiBaseUrl();
export const WS_URL: string = resolveWsUrl(API_BASE_URL);

export class ApiError extends Error {
  public readonly status: number;
  public readonly reasonCode: string;
  public readonly details: Record<string, unknown>;

  constructor(
    status: number,
    reasonCode: string,
    message: string,
    details: Record<string, unknown> = {}
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.reasonCode = reasonCode;
    this.details = details;
  }
}

export class ApiClient {
  static getToken(): string | null {
    try {
      return window.sessionStorage.getItem(TOKEN_STORAGE_KEY);
    } catch {
      return null;
    }
  }

  static setToken(token: string | null): void {
    try {
      if (token) {
        window.sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
      } else {
        window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
      }
    } catch {
      // ignore storage errors
    }
  }

  static async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = ApiClient.getToken();
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...(options.headers as Record<string, string> | undefined),
    };
    if (options.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const url = path.startsWith("http")
      ? path
      : `${API_BASE_URL}${path.startsWith("/") ? "" : "/"}${path}`;

    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        headers,
        credentials: "include",
      });
    } catch (networkErr) {
      throw new ApiError(
        0,
        "NETWORK_ERROR",
        "Không thể kết nối máy chủ. Vui lòng thử lại sau.",
        { originalError: String(networkErr) }
      );
    }

    let payload: Record<string, unknown> = {};
    try {
      payload = (await response.json()) as Record<string, unknown>;
    } catch {
      payload = {};
    }

    if (!response.ok) {
      const reasonCode =
        (payload.reason_code as string) ||
        (payload.error as string) ||
        `HTTP_${response.status}`;
      const message =
        (payload.message as string) ||
        (payload.detail as string) ||
        `Lỗi máy chủ (HTTP ${response.status})`;
      const details =
        (payload.details as Record<string, unknown>) || {};
      throw new ApiError(response.status, reasonCode, message, details);
    }

    return payload as unknown as T;
  }

  static get<T>(path: string, headers?: Record<string, string>): Promise<T> {
    return ApiClient.request<T>(path, { method: "GET", headers });
  }

  static post<T>(
    path: string,
    body?: unknown,
    headers?: Record<string, string>
  ): Promise<T> {
    return ApiClient.request<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
      headers,
    });
  }

  /**
   * Connect to FastAPI realtime WebSocket (/api/ws) with automatic SSE (/api/events/stream) fallback.
   */
  static subscribeRealtime(
    onEvent: (envelope: RealtimeEnvelope) => void,
    onStatusChange?: (connected: boolean) => void
  ): () => void {
    let closed = false;
    let ws: WebSocket | null = null;
    let sse: EventSource | null = null;
    let reconnectTimer: number | null = null;

    const cleanup = () => {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (ws) {
        try {
          ws.close();
        } catch {
          // ignore
        }
        ws = null;
      }
      if (sse) {
        try {
          sse.close();
        } catch {
          // ignore
        }
        sse = null;
      }
    };

    const connectSSE = () => {
      if (closed || sse) return;
      try {
        sse = new EventSource(`${API_BASE_URL}/api/events/stream`, {
          withCredentials: true,
        });
        sse.onopen = () => {
          onStatusChange?.(true);
        };
        sse.onmessage = (ev) => {
          try {
            const parsed = JSON.parse(ev.data) as RealtimeEnvelope;
            onEvent(parsed);
          } catch {
            // ignore malformed frame
          }
        };
        sse.onerror = () => {
          onStatusChange?.(false);
        };
      } catch {
        onStatusChange?.(false);
      }
    };

    const connectWS = () => {
      if (closed) return;
      try {
        ws = new WebSocket(WS_URL);
        ws.onopen = () => {
          if (sse) { sse.close(); sse = null; }
          onStatusChange?.(true);
        };
        ws.onmessage = (ev) => {
          try {
            const parsed = JSON.parse(ev.data) as RealtimeEnvelope;
            onEvent(parsed);
          } catch {
            // ignore malformed frame
          }
        };
        ws.onerror = () => {
          onStatusChange?.(false);
        };
        ws.onclose = () => {
          onStatusChange?.(sse?.readyState === 1);
          if (!closed) {
            connectSSE();
            reconnectTimer = window.setTimeout(connectWS, 10000);
          }
        };
      } catch {
        connectSSE();
      }
    };

    connectWS();

    return () => {
      closed = true;
      cleanup();
    };
  }
}
