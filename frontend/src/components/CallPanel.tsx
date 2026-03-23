import { useState } from "react";
import { Phone, PhoneOff, PhoneForwarded, X, Keyboard, ArrowLeft } from "lucide-react";
import { SoftKeyboard } from "./SoftKeyboard";
import type { CallState, Contact } from "../types";
import styles from "./CallPanel.module.css";

interface Props {
  callState: CallState;
  onCall: (address: string) => void;
  onHangup: () => void;
  onAnswer: () => void;
  onReject: () => void;
  contacts: Contact[];
}

export function CallPanel({ callState, onCall, onHangup, onAnswer, onReject, contacts }: Props) {
  const [address, setAddress] = useState("");
  const [mode, setMode] = useState<"idle" | "keyboard">("idle");

  const handleCall = (addr?: string) => {
    const target = addr || address.trim();
    if (target) {
      onCall(target);
      setAddress("");
      setMode("idle");
    }
  };

  const quickDials = contacts.filter((c) => c.quickDial);
  const isIdle = callState.state === "idle";
  const isIncoming = callState.state === "incoming";
  const isActive = !isIdle;

  return (
    <div className={styles.panel}>
      {/* ── Active Call ── */}
      {isActive && (
        <div className={`${styles.callDisplay} ${styles[callState.state]}`}>
          <div className={styles.stateRing}>
            <div className={`${styles.ringInner} ${callState.state === "connected" ? styles.ringConnected : callState.state === "incoming" ? styles.ringIncoming : styles.ringCalling}`}>
              {callState.state === "connected" ? (
                <Phone size={32} />
              ) : callState.state === "incoming" ? (
                <PhoneForwarded size={32} />
              ) : (
                <Phone size={32} />
              )}
            </div>
          </div>
          <div className={styles.stateLabel}>
            {callState.state === "calling" && "Calling"}
            {callState.state === "ringing" && "Ringing"}
            {callState.state === "incoming" && "Incoming Call"}
            {callState.state === "connected" && "On Air"}
          </div>
          <div className={styles.destination}>{callState.destination || "Unknown"}</div>

          <div className={styles.callBtnRow}>
            {isIncoming ? (
              <>
                <button className={styles.bigBtnGreen} onClick={onAnswer}>
                  <Phone size={24} />
                  <span>Accept</span>
                </button>
                <button className={styles.bigBtnRed} onClick={onReject}>
                  <X size={24} />
                  <span>Reject</span>
                </button>
              </>
            ) : (
              <button className={styles.bigBtnRed} onClick={onHangup}>
                <PhoneOff size={24} />
                <span>End Call</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Idle: Quick Dial View ── */}
      {isIdle && mode === "idle" && (
        <div className={styles.idlePanel}>
          <div className={styles.idleStatus}>
            <div className={styles.readyDot} />
            <span>Ready</span>
          </div>

          {quickDials.length > 0 && (
            <div className={styles.quickGrid}>
              {quickDials.map((c) => (
                <button
                  key={c.id}
                  className={styles.quickBtn}
                  onClick={() => handleCall(c.address)}
                >
                  <PhoneForwarded size={20} className={styles.quickIcon} />
                  <span className={styles.quickName}>{c.name}</span>
                  <span className={styles.quickAddr}>{c.address}</span>
                </button>
              ))}
            </div>
          )}

          {contacts.length > 0 && quickDials.length === 0 && (
            <div className={styles.quickGrid}>
              {contacts.slice(0, 6).map((c) => (
                <button
                  key={c.id}
                  className={styles.quickBtn}
                  onClick={() => handleCall(c.address)}
                >
                  <PhoneForwarded size={20} className={styles.quickIcon} />
                  <span className={styles.quickName}>{c.name}</span>
                  <span className={styles.quickAddr}>{c.address}</span>
                </button>
              ))}
            </div>
          )}

          {contacts.length === 0 && (
            <div className={styles.emptyHint}>
              Add contacts in the Contacts tab for quick dial buttons
            </div>
          )}

          <button className={styles.keyboardBtn} onClick={() => setMode("keyboard")}>
            <Keyboard size={20} />
            <span>Dial Address</span>
          </button>
        </div>
      )}

      {/* ── Keyboard: Manual Address Entry ── */}
      {isIdle && mode === "keyboard" && (
        <div className={styles.keyboardPanel}>
          <button className={styles.backBtn} onClick={() => { setMode("idle"); setAddress(""); }}>
            <ArrowLeft size={18} />
            <span>Back</span>
          </button>

          <div className={styles.addressDisplay} onClick={() => document.getElementById("addr-input")?.focus()}>
            <span className={styles.addressPrefix}>sip:</span>
            <span className={styles.addressText}>{address || "—"}</span>
            <input
              id="addr-input"
              className={styles.hiddenInput}
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCall();
                if (e.key === "Escape") { setMode("idle"); setAddress(""); }
              }}
              autoFocus
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
            />
          </div>

          <SoftKeyboard
            onKey={(char) => setAddress((prev) => prev + char)}
            onBackspace={() => setAddress((prev) => prev.slice(0, -1))}
            onClear={() => setAddress("")}
            onSubmit={() => handleCall()}
          />

          <div className={styles.callBtnRow}>
            <button
              className={styles.bigBtnGreen}
              onClick={() => handleCall()}
              disabled={!address.trim()}
            >
              <Phone size={24} />
              <span>Call</span>
            </button>
            <button
              className={styles.bigBtnMuted}
              onClick={() => setAddress("")}
            >
              <X size={24} />
              <span>Clear</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
