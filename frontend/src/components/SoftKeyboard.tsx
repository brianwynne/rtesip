import { Delete, CornerDownLeft } from "lucide-react";
import { useState } from "react";
import styles from "./SoftKeyboard.module.css";

interface Props {
  onKey: (char: string) => void;
  onBackspace: () => void;
  onClear: () => void;
  onSubmit?: () => void;
  domains?: string[];
}

const ROWS_LOWER = [
  ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
  ["z", "x", "c", "v", "b", "n", "m"],
];

const ROWS_UPPER = [
  ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
  ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
  ["Z", "X", "C", "V", "B", "N", "M"],
];

const NUM_ROW = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"];
const SIP_ROW = ["@", ".", "-", "_", ":", "+", "/"];
const SYM_ROWS = [
  ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")"],
  ["-", "_", "=", "+", "[", "]", "{", "}", "\\", "|"],
  ["`", "~", ";", ":", "'", "\"", ",", ".", "/", "?"],
  ["<", ">"]
];

const DEFAULT_DOMAINS = ["@sip.rtegroup.ie", "@sip.audio"];

export function SoftKeyboard({ onKey, onBackspace, onSubmit, domains }: Props) {
  const sipDomains = domains ?? DEFAULT_DOMAINS;
  const [shifted, setShifted] = useState(false);
  const [showSymbols, setShowSymbols] = useState(false);

  const rows = shifted ? ROWS_UPPER : ROWS_LOWER;

  const handleKey = (char: string) => {
    onKey(char);
    if (shifted) setShifted(false);
  };

  // Prevent buttons stealing focus from the hidden input
  const prevent = (e: React.PointerEvent | React.MouseEvent) => e.preventDefault();

  return (
    <div className={styles.keyboard}>
      {/* Domain shortcuts */}
      {sipDomains.length > 0 && (
        <div className={styles.domainRow}>
          {sipDomains.map((d) => (
            <button key={d} className={styles.domainBtn} onPointerDown={prevent} onClick={() => onKey(d)}>
              {d}
            </button>
          ))}
        </div>
      )}

      {/* Number row */}
      <div className={styles.row}>
        {NUM_ROW.map((k) => (
          <button key={k} className={styles.key} onPointerDown={prevent} onClick={() => handleKey(k)}>
            {k}
          </button>
        ))}
      </div>

      {showSymbols ? (
        <>
          {SYM_ROWS.map((row, i) => (
            <div key={`sym-${i}`} className={styles.row}>
              {row.map((k) => (
                <button key={k} className={styles.key} onPointerDown={prevent} onClick={() => handleKey(k)}>
                  {k}
                </button>
              ))}
              {i === 3 && (
                <>
                  <button className={`${styles.key} ${styles.keyFlex}`} onPointerDown={prevent} onClick={() => handleKey(" ")}>
                    space
                  </button>
                  <button className={`${styles.key} ${styles.keyWide}`} onPointerDown={prevent} onClick={onBackspace}>
                    <Delete size={18} />
                  </button>
                </>
              )}
            </div>
          ))}
          <div className={styles.row}>
            <button className={`${styles.key} ${styles.keyWide}`} onPointerDown={prevent} onClick={() => setShowSymbols(false)}>
              ABC
            </button>
            {onSubmit && (
              <button className={`${styles.key} ${styles.keyCall}`} onPointerDown={prevent} onClick={onSubmit}>
                <CornerDownLeft size={18} />
              </button>
            )}
          </div>
        </>
      ) : (
        <>
          {/* Letter rows */}
          {rows.map((row, i) => (
            <div key={i} className={styles.row}>
              {i === 2 && (
                <button
                  className={`${styles.key} ${styles.keyWide} ${shifted ? styles.keyActive : ""}`}
                  onPointerDown={prevent}
                  onClick={() => setShifted(!shifted)}
                >
                  &#8679;
                </button>
              )}
              {row.map((k) => (
                <button key={k} className={styles.key} onPointerDown={prevent} onClick={() => handleKey(k)}>
                  {k}
                </button>
              ))}
              {i === 2 && (
                <button className={`${styles.key} ${styles.keyWide}`} onPointerDown={prevent} onClick={onBackspace}>
                  <Delete size={18} />
                </button>
              )}
            </div>
          ))}

          {/* Bottom row */}
          <div className={styles.row}>
            <button className={`${styles.key} ${styles.keyWide}`} onPointerDown={prevent} onClick={() => setShowSymbols(true)}>
              @._
            </button>
            <button className={`${styles.key} ${styles.keySip}`} onPointerDown={prevent} onClick={() => handleKey("@")}>
              @
            </button>
            <button className={`${styles.key} ${styles.keyFlex}`} onPointerDown={prevent} onClick={() => handleKey(".")}>
              .
            </button>
            <button className={`${styles.key} ${styles.keySip}`} onPointerDown={prevent} onClick={() => handleKey("-")}>
              -
            </button>
            {onSubmit && (
              <button className={`${styles.key} ${styles.keyCall}`} onPointerDown={prevent} onClick={onSubmit}>
                <CornerDownLeft size={18} />
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
