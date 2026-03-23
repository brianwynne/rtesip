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
        send({ command: "authRequest" });
      };

      ws.onmessage = (e) => {
        const msg: WsMessage = JSON.parse(e.data);

        switch (msg.event) {
          case "challenge":
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

  // --- Volume control with local-first state ---

  const setLevel = useCallback((type: "vol" | "gain", channel: "l" | "r", level: number) => {
    const clamped = Math.max(0, Math.min(150, level));
    setVolume((prev) => {
      const next = { ...prev };
      if (type === "gain") {
        if (channel === "l") next.cl = clamped;
        if (channel === "r") next.cr = clamped;
        if (prev.clink) { next.cl = clamped; next.cr = clamped; }
      } else {
        if (channel === "l") next.pl = clamped;
        if (channel === "r") next.pr = clamped;
        if (prev.plink) { next.pl = clamped; next.pr = clamped; }
      }
      return next;
    });
    send({ command: type === "vol" ? "vol" : "gain", channel, level: clamped });
  }, [send]);

  const adjustLevel = useCallback((type: "vol" | "gain", channel: "l" | "r", direction: "up" | "down") => {
    setVolume((prev) => {
      const next = { ...prev };
      const delta = direction === "up" ? 10 : -10;
      if (type === "gain") {
        const newL = Math.max(0, Math.min(150, prev.cl + delta));
        const newR = Math.max(0, Math.min(150, prev.cr + delta));
        if (channel === "l" || prev.clink) next.cl = newL;
        if (channel === "r" || prev.clink) next.cr = prev.clink ? newL : newR;
      } else {
        const newL = Math.max(0, Math.min(150, prev.pl + delta));
        const newR = Math.max(0, Math.min(150, prev.pr + delta));
        if (channel === "l" || prev.plink) next.pl = newL;
        if (channel === "r" || prev.plink) next.pr = prev.plink ? newL : newR;
      }
      return next;
    });
    send({ command: type === "vol" ? "vol" : "gain", channel, direction });
  }, [send]);

  const muteToggle = useCallback((which: "vol" | "gain") => {
    setVolume((prev) => {
      const next = { ...prev };
      if (which === "gain") {
        if (prev.cl === 0 && prev.cr === 0) {
          next.cl = 100; next.cr = 100;
        } else {
          next.cl = 0; next.cr = 0;
        }
      } else {
        if (prev.pl === 0 && prev.pr === 0) {
          next.pl = 100; next.pr = 100;
        } else {
          next.pl = 0; next.pr = 0;
        }
      }
      return next;
    });
    send({ command: "mute", which });
  }, [send]);

  const toggleLink = useCallback((type: "vol" | "gain", linked: boolean) => {
    setVolume((prev) => {
      const next = { ...prev };
      if (type === "gain") {
        next.clink = linked;
        if (linked) {
          const avg = Math.round((prev.cl + prev.cr) / 20) * 10;
          next.cl = avg; next.cr = avg;
        }
      } else {
        next.plink = linked;
        if (linked) {
          const avg = Math.round((prev.pl + prev.pr) / 20) * 10;
          next.pl = avg; next.pr = avg;
        }
      }
      return next;
    });
    send({ command: type === "vol" ? "vol" : "gain", link: linked });
  }, [send]);

  return {
    connected, authed, callState, accounts, volume, sipReady,
    send, authenticate,
    call: (address: string) => send({ command: "call", address }),
    hangup: () => send({ command: "hangup" }),
    answer: () => send({ command: "answer" }),
    reject: () => send({ command: "reject" }),
    setVol: (channel: "l" | "r", direction: "up" | "down") => adjustLevel("vol", channel, direction),
    setGain: (channel: "l" | "r", direction: "up" | "down") => adjustLevel("gain", channel, direction),
    setVolLevel: (channel: "l" | "r", level: number) => setLevel("vol", channel, level),
    setGainLevel: (channel: "l" | "r", level: number) => setLevel("gain", channel, level),
    mute: muteToggle,
    toggleLink,
  };
}
