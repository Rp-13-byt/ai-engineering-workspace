import { useEffect, useRef, useState } from "react";

type RealtimeStatus = "offline" | "connecting" | "online";

type RealtimeEvent = 
  | { type: "online"; online: number }
  | { type: "task.updated"; task_id: string }
  | { type: "repository.updated"; repository_id: string }
  | { type: string; [key: string]: any };

type Listener = (event: RealtimeEvent) => void;

class RealtimeClient {
  private socket: WebSocket | null = null;
  private listeners: Set<Listener> = new Set();
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;

  public status: RealtimeStatus = "offline";
  public onlineCount: number = 0;

  constructor(private url: string) {}

  public subscribe(listener: Listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  public connect() {
    if (this.socket) return;
    this.status = "connecting";
    this.notify({ type: "status.changed", status: this.status });

    this.socket = new WebSocket(this.url);

    this.socket.onopen = () => {
      this.status = "online";
      this.notify({ type: "status.changed", status: this.status });
      this.heartbeatTimer = window.setInterval(() => {
        this.socket?.send(JSON.stringify({ type: "heartbeat" }));
      }, 25000);
    };

    this.socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data);
        if (event.type === "online") {
          this.onlineCount = event.online;
          this.notify(event);
        } else {
          this.notify(event);
        }
      } catch (e) {
        console.error("Failed to parse websocket message", e);
      }
    };

    this.socket.onclose = () => {
      this.status = "offline";
      this.socket = null;
      this.notify({ type: "status.changed", status: this.status });
      if (this.heartbeatTimer) window.clearInterval(this.heartbeatTimer);
      this.reconnectTimer = window.setTimeout(() => this.connect(), 1500);
    };
  }

  public disconnect() {
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);
    if (this.heartbeatTimer) window.clearInterval(this.heartbeatTimer);
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
    this.status = "offline";
    this.notify({ type: "status.changed", status: this.status });
  }

  public send(event: Record<string, any>) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(event));
    }
  }

  private notify(event: any) {
    this.listeners.forEach((l) => l(event));
  }
}

export function useRealtime(organizationId: string, token: string | null) {
  const [status, setStatus] = useState<RealtimeStatus>("offline");
  const [onlineCount, setOnlineCount] = useState(0);
  const clientRef = useRef<RealtimeClient | null>(null);

  useEffect(() => {
    if (!token) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
    const client = new RealtimeClient(`${wsUrl}/${organizationId}?token=${encodeURIComponent(token)}`);
    clientRef.current = client;

    const unsubscribe = client.subscribe((event) => {
      if (event.type === "status.changed") {
        setStatus(client.status);
      } else if (event.type === "online") {
        setOnlineCount(event.online);
      }
    });

    client.connect();

    return () => {
      unsubscribe();
      client.disconnect();
    };
  }, [organizationId, token]);

  useEffect(() => {
    if (clientRef.current) {
      setStatus(clientRef.current.status);
      setOnlineCount(clientRef.current.onlineCount);
    }
  }, []);

  return {
    status,
    onlineCount,
    subscribe: (listener: Listener) => {
      if (clientRef.current) {
        return clientRef.current.subscribe(listener);
      }
      return () => {};
    },
    sendEvent: (event: Record<string, any>) => {
      clientRef.current?.send(event);
    }
  };
}
