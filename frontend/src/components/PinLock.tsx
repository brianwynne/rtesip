import { useState, useEffect } from "react";
import { Lock, Delete } from "lucide-react";
import { Logo } from "./Logo";
import styles from "./PinLock.module.css";

interface Props {
  onUnlock: () => void;
}

export function PinLock({ onUnlock }: Props) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState(false);
  const [checking, setChecking] = useState(false);

  const handleDigit = (d: string) => {
    if (pin.length < 8) {
      setPin((p) => p + d);
      setError(false);
    }
  };

  const handleDelete = () => {
    setPin((p) => p.slice(0, -1));
    setError(false);
  };

  const handleClear = () => {
    setPin("");
    setError(false);
  };

  useEffect(() => {
    if (pin.length >= 6) {
      setChecking(true);
      fetch("/api/system/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
      })
        .then((r) => {
          if (r.ok) {
            onUnlock();
          } else {
            setError(true);
            setPin("");
          }
          setChecking(false);
        })
        .catch(() => {
          setError(true);
          setPin("");
          setChecking(false);
        });
    }
  }, [pin, onUnlock]);

  return (
    <div className={styles.overlay}>
      <div className={styles.container}>
        <Logo size="large" />
        <div className={styles.title}>SIP Reporter</div>

        <div className={styles.lockIcon}>
          <Lock size={32} />
        </div>

        <div className={styles.dots}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className={`${styles.dot} ${i < pin.length ? styles.dotFilled : ""} ${error ? styles.dotError : ""}`}
            />
          ))}
        </div>

        {error && <div className={styles.errorText}>Incorrect PIN</div>}
        {checking && <div className={styles.checkingText}>Checking...</div>}

        <div className={styles.keypad}>
          {["1", "2", "3", "4", "5", "6", "7", "8", "9", "CLR", "0", "DEL"].map((key) => (
            <button
              key={key}
              className={`${styles.key} ${key === "CLR" || key === "DEL" ? styles.keyAction : ""}`}
              onClick={() => {
                if (key === "DEL") handleDelete();
                else if (key === "CLR") handleClear();
                else handleDigit(key);
              }}
            >
              {key === "DEL" ? <Delete size={24} /> : key}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
