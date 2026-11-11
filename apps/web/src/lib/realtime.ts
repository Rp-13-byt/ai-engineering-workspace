import { useEffect, useRef, useState } from "react";

type RealtimeStatus = "offline" | "connecting" | "online";

export function useRealtime(organizationId: string, token: string | null) {
  const [status, setStatus] = useState<RealtimeStatus>("offline");
  const [onlineCount, setOnlineCount] = useState(0);
  const heartbeatRef = useRef<number | null>(null);

  useEffect(() => {
    if (!token) return;

    let closedByClient = false;
    let reconnectTimer: number | null = null;

    const connect = () => {
      setStatus("connecting");
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
      const socket = new WebSocket(`${wsUrl}/${organizationId}?token=${encodeURIComponent(token)}`);

      socket.onopen = () => {
        setStatus("online");
        heartbeatRef.current = window.setInterval(() => {
          socket.send(JSON.stringify({ type: "heartbeat" }));
        }, 25000);
      };

      socket.onmessage = (message) => {
        const event = JSON.parse(message.data);
        if (typeof event.online === "number") {
          setOnlineCount(event.online);
        }
      };

      socket.onclose = () => {
        setStatus("offline");
        if (heartbeatRef.current) window.clearInterval(heartbeatRef.current);
        if (!closedByClient) {
          reconnectTimer = window.setTimeout(connect, 1500);
        }
      };
    };

    connect();
    return () => {
      closedByClient = true;
      if (heartbeatRef.current) window.clearInterval(heartbeatRef.current);
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
    };
  }, [organizationId, token]);

  return { status, onlineCount };
}
