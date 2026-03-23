import { useState } from "react";
import { Phone, PhoneForwarded, X, Keyboard, User } from "lucide-react";
import { SoftKeyboard } from "./SoftKeyboard";
import { CallInfo } from "./CallInfo";
import type { CallState, Contact } from "../types";
import styles from "./CallPanel.module.css";

interface Props {
  callState: CallState;
  sipReady: boolean;
  onCall: (address: string) => void;
  onHangup: () => void;
  onAnswer: () => void;
  onReject: () => void;
  contacts: Contact[];
}

export function CallPanel({ callState, sipReady, onCall, onHangup, onAnswer, onReject, contacts }: Props) {
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

  return (
    <div className={styles.panel}>
      {/* ── Call Info Display ── */}
      <div className={styles.displayArea}>
        <CallInfo callState={callState} sipReady={sipReady} onHangup={onHangup} />
      </div>

      {/* ── Incoming call accept/reject ── */}
      {isIncoming && (
        <div className={styles.callBtnRow}>
          <button className={styles.bigBtnGreen} onClick={onAnswer}>
            <Phone size={20} />
            <span>Accept</span>
          </button>
          <button className={styles.bigBtnRed} onClick={onReject}>
            <X size={20} />
            <span>Reject</span>
          </button>
        </div>
      )}

      {/* ── Quick Dial + Keyboard Overlay ── */}
      {!isIncoming && (
        <div className={styles.idlePanel}>

          <div className={styles.quickGrid}>
            {Array.from({ length: 8 }).map((_, i) => {
              const contact = quickDials[i] || (quickDials.length === 0 ? contacts[i] : undefined);
              if (contact) {
                return (
                  <button
                    key={contact.id}
                    className={styles.quickBtn}
                    onClick={() => handleCall(contact.address)}
                  >
                    <PhoneForwarded size={18} className={styles.quickIcon} />
                    <span className={styles.quickName}>{contact.name}</span>
                    <span className={styles.quickAddr}>{contact.address}</span>
                  </button>
                );
              }
              return (
                <div key={`empty-${i}`} className={styles.quickBtnEmpty}>
                  <User size={18} className={styles.emptyIcon} />
                  <span className={styles.emptyLabel}>{i + 1}</span>
                </div>
              );
            })}
          </div>

          <button className={styles.keyboardBtn} onClick={() => setMode("keyboard")}>
            <Keyboard size={20} />
            <span>Dial Address</span>
          </button>
        </div>
      )}

      {/* Keyboard overlay — anchored to panel, outside flex flow */}
      {isIdle && mode === "keyboard" && (
        <div className={styles.keyboardOverlay}>
          <div className={styles.overlayHeader}>
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
            <button className={styles.overlayClose} onClick={() => { setMode("idle"); setAddress(""); }}>
              <X size={16} />
            </button>
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
