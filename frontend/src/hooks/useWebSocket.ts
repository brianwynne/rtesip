import { useCallback, useEffect, useRef, useState } from "react";
import type { CallState, VolumeState, AccountStatus, WsMessage } from "../types";

const WS_URL = `ws://${window.location.host}/ws`;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number>();
  const [connected, setConnected] = useState(false);
  const [authed, setAuthed] = useState(false);

  const [callState, setCallState] = useState<CallState>({ state: "idle" });
  const [accounts, setAccounts] = useState<Record<string, AccountStatus>>({});
  const [volume, setVolume] = useState<VolumeState>({
    cl: 100, cr: 100, clink: false,
    pl: 100, pr: 100, plink: false,
  });
  const [sipReady, setSipReady] = useState(false);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const authenticate = useCallback((password: string) => {
    send({ command: "authRequest" });
    const handler = (e: MessageEvent) => {
      const msg: WsMessage = JSON.parse(e.data);
      if (msg.event === "challenge") {
        const challenge = msg.challenge as string;
        crypto.subtle
          .digest("SHA-256", new TextEncoder().encode(password + challenge))
          .then((buf) => {
            const hash = Array.from(new Uint8Array(buf))
              .map((b) => b.toString(16).padStart(2, "0"))
              .join("");
            send({ command: "challengeResponse", response: hash });
          });
        wsRef.current?.removeEventListener("message", handler);
      }
    };
    wsRef.current?.addEventListener("message", handler);
  }, [send]);

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        // Auto-auth with empty password (no password set = auto-accept)
        send({ command: "authRequest" });
      };

      ws.onmessage = (e) => {
        const msg: WsMessage = JSON.parse(e.data);

        switch (msg.event) {
          case "challenge":
            // No password — respond with hash of empty string + challenge
            crypto.subtle
              .digest("SHA-256", new TextEncoder().encode(String(msg.challenge)))
              .then((buf) => {
                const hash = Array.from(new Uint8Array(buf))
                  .map((b) => b.toString(16).padStart(2, "0"))
                  .join("");
                send({ command: "challengeResponse", response: hash });
              });
            break;

          case "state":
            setAuthed(true);
            setSipReady(msg.sip_ready as boolean);
            if (msg.call_state) {
              setCallState({
                state: msg.call_state as CallState["state"],
                destination: msg.current_contact as string,
              });
            }
            break;

          case "notAuthed":
            setAuthed(false);
            break;

          case "levels":
            setVolume({
              cl: msg.cl as number, cr: msg.cr as number, clink: !!msg.clink,
              pl: msg.pl as number, pr: msg.pr as number, plink: !!msg.plink,
            });
            break;

          case "account": {
            const acc = msg as unknown as AccountStatus & { event: string };
            setAccounts((prev) => ({ ...prev, [acc.id]: acc }));
            break;
          }

          case "calling":
          case "trying":
            setCallState({ state: "calling", destination: msg.destination as string });
            break;
          case "ringing":
            setCallState({ state: "ringing", destination: msg.destination as string });
            break;
          case "incoming":
            setCallState({ state: "incoming", destination: msg.destination as string });
            break;
          case "connected":
            setCallState({ state: "connected", destination: msg.destination as string });
            break;
          case "ended":
            setCallState({ state: "idle" });
            break;
        }
      };

      ws.onclose = () => {
        setConnected(false);
        setAuthed(false);
        reconnectTimer.current = window.setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    connected, authed, callState, accounts, volume, sipReady,
    send, authenticate,
    call: (address: string) => send({ command: "call", address }),
    hangup: () => send({ command: "hangup" }),
    answer: () => send({ command: "answer" }),
    reject: () => send({ command: "reject" }),
    setVol: (channel: "l" | "r", direction: "up" | "down") =>
      send({ command: "vol", channel, direction }),
    setGain: (channel: "l" | "r", direction: "up" | "down") =>
      send({ command: "gain", channel, direction }),
    mute: (which: "vol" | "gain") => send({ command: "mute", which }),
    toggleLink: (type: "vol" | "gain", linked: boolean) =>
      send({ command: type === "vol" ? "vol" : "gain", link: linked }),
  };
}
