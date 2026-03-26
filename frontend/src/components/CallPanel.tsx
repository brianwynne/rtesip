import { useState } from "react";
import { Phone, PhoneForwarded, X, Keyboard, User, ChevronLeft, ChevronRight } from "lucide-react";
import { SoftKeyboard } from "./SoftKeyboard";
import { CallInfo } from "./CallInfo";
import type { CallState, Contact } from "../types";
import styles from "./CallPanel.module.css";

const PAGE_SIZE = 4;

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
  const [page, setPage] = useState(0);

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

          <div className={styles.quickSection}>
            {page > 0 && (
              <button className={styles.pageBtn} onClick={() => setPage(page - 1)}>
                <ChevronLeft size={28} />
              </button>
            )}
            <div className={styles.quickGrid}>
              {Array.from({ length: PAGE_SIZE }).map((_, i) => {
                const idx = page * PAGE_SIZE + i;
                const allContacts = quickDials.length > 0 ? quickDials : contacts;
                const contact = allContacts[idx];
                if (contact) {
                  return (
                    <button
                      key={contact.id}
                      className={styles.quickBtn}
                      onClick={() => handleCall(contact.address)}
                    >
                      <PhoneForwarded size={18} className={styles.quickIcon} />
                      <span className={styles.quickName}>{contact.name}</span>
                    </button>
                  );
                }
                return (
                  <div key={`empty-${i}`} className={styles.quickBtnEmpty}>
                    <User size={28} className={styles.emptyIcon} />
                    <span className={styles.emptyLabel}>{idx + 1}</span>
                  </div>
                );
              })}
            </div>
            {(() => {
              const allContacts = quickDials.length > 0 ? quickDials : contacts;
              const totalPages = Math.max(1, Math.ceil(allContacts.length / PAGE_SIZE));
              return page < totalPages - 1 ? (
                <button className={styles.pageBtn} onClick={() => setPage(page + 1)}>
                  <ChevronRight size={28} />
                </button>
              ) : <div className={styles.pageBtnSpacer} />;
            })()}
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
