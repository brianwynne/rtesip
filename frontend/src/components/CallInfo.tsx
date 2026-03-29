import { useState, useEffect } from "react";
import { PhoneOff, Shield, ShieldOff, Wifi } from "lucide-react";
import type { CallState } from "../types";
import styles from "./CallInfo.module.css";

interface Props {
  callState: CallState;
  sipReady: boolean;
  onHangup: () => void;
}

export function CallInfo({ callState, sipReady, onHangup }: Props) {
  const [now, setNow] = useState(new Date());
  const [duration, setDuration] = useState(0);
  const [confirmHangup, setConfirmHangup] = useState(false);

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (callState.state === "connected" && callState.connectedAt) {
      // Use server timestamp — survives page reloads
      const serverEpochMs = callState.connectedAt * 1000;
      const t = setInterval(() => {
        setDuration(Math.floor((Date.now() - serverEpochMs) / 1000));
      }, 1000);
      // Set immediately
      setDuration(Math.floor((Date.now() - serverEpochMs) / 1000));
      return () => clearInterval(t);
    } else if (callState.state !== "connected") {
      setDuration(0);
    }
  }, [callState.state, callState.connectedAt]);

  useEffect(() => {
    if (confirmHangup) {
      const t = setTimeout(() => setConfirmHangup(false), 3000);
      return () => clearTimeout(t);
    }
  }, [confirmHangup]);

  const formatTime = (d: Date) =>
    d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

  const formatDuration = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };

  const isActive = callState.state !== "idle";
  const isConnected = callState.state === "connected";
  const isIncoming = callState.state === "incoming";
  const isCalling = callState.state === "calling" || callState.state === "ringing";

  // Parse destination into display name and domain
  const HOME_DOMAIN = "sip.rtegroup.ie";
  const dest = callState.destination || "";
  let displayName = dest;
  let displayDomain = "";

  // Parse SIP address: "Display Name <sip:user@domain>" or "user@domain"
  if (dest.includes("@")) {
    let addr = dest;
    let name = "";
    // Extract display name from "Name <sip:...>" format
    const angleMatch = dest.match(/^"?([^"<]+)"?\s*<(.+)>$/);
    if (angleMatch) {
      name = angleMatch[1].trim();
      addr = angleMatch[2];
    }
    // Strip sip: prefix and any ;params
    addr = addr.replace(/^sip:/i, "").replace(/;.*$/, "");
    const [user, domain] = addr.split("@", 2);
    displayName = name || user;
    displayDomain = domain === HOME_DOMAIN ? "" : domain;
  }

  return (
    <div className={`${styles.display} ${isConnected ? styles.displayConnected : isIncoming ? styles.displayIncoming : isCalling ? styles.displayCalling : ""}`}>
      {/* Top: status + clock */}
      <div className={styles.topRow}>
        <div className={styles.topLeft}>
          <div className={`${styles.statusDot} ${isConnected ? styles.dotLive : isActive ? styles.dotActive : styles.dotIdle}`} />
          <span className={`${styles.stateLabel} ${isConnected ? styles.stateLabelLive : isIncoming ? styles.stateLabelIncoming : ""}`}>
            {isConnected && "On Air"}
            {isIncoming && "Incoming"}
            {isCalling && "Calling"}
            {!isActive && "Standby"}
          </span>
          {isConnected && (
            <span className={styles.durationInline}>{formatDuration(duration)}</span>
          )}
        </div>
        <span className={styles.clock}>{formatTime(now)}</span>
      </div>

      {/* Centre: party name */}
      <div className={styles.partyRow}>
        {isActive ? (
          <>
            <span className={styles.partyName}>{displayName || "Unknown"}</span>
            {displayDomain && <span className={styles.partyDomain}>{displayDomain}</span>}
          </>
        ) : (
          <span className={styles.partyNameIdle}>No active call</span>
        )}
      </div>

      {/* Bottom: metadata */}
      <div className={styles.bottomRow}>
        <div className={styles.metaGroup}>
          <div className={styles.meta}>
            {sipReady ? <Shield size={14} className={styles.iconGreen} /> : <ShieldOff size={14} />}
            <span>{sipReady ? "TLS" : "TCP"}</span>
          </div>
          <div className={styles.meta}>
            <Wifi size={14} />
            <span>{callState.codec || "—"}</span>
          </div>
        </div>
      </div>

      {/* Hangup button — positioned under the clock */}
      {isActive && (
        <button
          className={`${styles.hangupBtn} ${confirmHangup ? styles.hangupConfirm : ""}`}
          onClick={() => {
            if (confirmHangup) { onHangup(); setConfirmHangup(false); }
            else setConfirmHangup(true);
          }}
        >
          <PhoneOff size={18} />
          <span>{confirmHangup ? "Confirm" : "End"}</span>
        </button>
      )}
    </div>
  );
}
