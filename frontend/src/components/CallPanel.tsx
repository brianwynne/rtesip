import { useState, useRef } from "react";
import { Phone, PhoneOff, PhoneForwarded, X, Search } from "lucide-react";
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
  const [showContacts, setShowContacts] = useState(false);
  const [filter, setFilter] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleCall = () => {
    if (address.trim()) {
      onCall(address.trim());
      setAddress("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleCall();
  };

  const filteredContacts = contacts.filter(
    (c) =>
      c.name.toLowerCase().includes(filter.toLowerCase()) ||
      c.address.toLowerCase().includes(filter.toLowerCase())
  );

  const isIdle = callState.state === "idle";
  const isIncoming = callState.state === "incoming";
  const isActive = !isIdle;

  return (
    <div className={styles.panel}>
      {/* Active call display */}
      {isActive && (
        <div className={`${styles.callActive} ${styles[callState.state]}`}>
          <div className={styles.callStateLabel}>
            {callState.state === "calling" && "Calling..."}
            {callState.state === "ringing" && "Ringing..."}
            {callState.state === "incoming" && "Incoming Call"}
            {callState.state === "connected" && "Connected"}
          </div>
          <div className={styles.callDestination}>{callState.destination || "Unknown"}</div>
          <div className={styles.callActions}>
            {isIncoming && (
              <>
                <button className={styles.answerBtn} onClick={onAnswer}>
                  <Phone size={20} />
                  <span>Accept</span>
                </button>
                <button className={styles.rejectBtn} onClick={onReject}>
                  <X size={20} />
                  <span>Reject</span>
                </button>
              </>
            )}
            {!isIncoming && (
              <button className={styles.hangupBtn} onClick={onHangup}>
                <PhoneOff size={20} />
                <span>Hang Up</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Dial pad */}
      {isIdle && (
        <div className={styles.dialSection}>
          <div className={styles.dialRow}>
            <input
              ref={inputRef}
              className={styles.dialInput}
              type="text"
              placeholder="Enter SIP address..."
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              onKeyDown={handleKeyDown}
              autoComplete="off"
            />
            <button
              className={styles.dialBtn}
              onClick={handleCall}
              disabled={!address.trim()}
            >
              <Phone size={18} />
            </button>
            <button
              className={styles.contactsBtn}
              onClick={() => setShowContacts(!showContacts)}
            >
              <Search size={18} />
            </button>
          </div>

          {/* Quick dial */}
          {!showContacts && contacts.filter((c) => c.quickDial).length > 0 && (
            <div className={styles.quickDial}>
              {contacts
                .filter((c) => c.quickDial)
                .map((c) => (
                  <button
                    key={c.id}
                    className={styles.quickDialBtn}
                    onClick={() => onCall(c.address)}
                  >
                    <PhoneForwarded size={14} />
                    <span>{c.name}</span>
                  </button>
                ))}
            </div>
          )}

          {/* Contact list */}
          {showContacts && (
            <div className={styles.contactList}>
              <input
                className={styles.contactFilter}
                type="text"
                placeholder="Filter contacts..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                autoFocus
              />
              <div className={styles.contactScroll}>
                {filteredContacts.map((c) => (
                  <button
                    key={c.id}
                    className={styles.contactItem}
                    onClick={() => {
                      onCall(c.address);
                      setShowContacts(false);
                      setFilter("");
                    }}
                  >
                    <span className={styles.contactName}>{c.name}</span>
                    <span className={styles.contactAddr}>{c.address}</span>
                  </button>
                ))}
                {filteredContacts.length === 0 && (
                  <div className={styles.noContacts}>No contacts found</div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
