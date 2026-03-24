import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./FaderSlider.module.css";

interface Props {
  level: number;
  maxLevel?: number;
  muted?: boolean;
  onChange: (level: number) => void;
}

const TICKS = [
  { pct: 100, label: "100" },
  { pct: 75, label: "75" },
  { pct: 50, label: "50" },
  { pct: 25, label: "25" },
  { pct: 0, label: "0" },
];

export function FaderSlider({ level, maxLevel = 150, muted, onChange }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const [localLevel, setLocalLevel] = useState(level);

  // Sync from parent when not dragging
  useEffect(() => {
    if (!dragging.current) {
      setLocalLevel(level);
    }
  }, [level]);

  const levelFromY = useCallback((clientY: number) => {
    const track = trackRef.current;
    if (!track) return localLevel;
    const rect = track.getBoundingClientRect();
    const pct = 1 - (clientY - rect.top) / rect.height;
    return Math.round(Math.max(0, Math.min(maxLevel, pct * maxLevel)));
  }, [localLevel, maxLevel]);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    dragging.current = true;
    trackRef.current?.setPointerCapture(e.pointerId);
    const newLevel = levelFromY(e.clientY);
    setLocalLevel(newLevel);
    onChange(newLevel);
  }, [levelFromY, onChange]);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging.current) return;
    const newLevel = levelFromY(e.clientY);
    setLocalLevel(newLevel);
    onChange(newLevel);
  }, [levelFromY, onChange]);

  const onPointerUp = useCallback(() => {
    dragging.current = false;
  }, []);

  const pct = Math.min(100, (localLevel / maxLevel) * 100);
  const knobBottom = `calc(${pct}% - 0.7rem)`;

  return (
    <div className={styles.faderStrip}>
      {/* Scale labels */}
      <div className={styles.scale}>
        {TICKS.map((t) => (
          <span key={t.label} className={styles.scaleLabel} style={{ bottom: `${t.pct}%` }}>
            {t.label}
          </span>
        ))}
      </div>

      {/* Track — all pointer events on this element */}
      <div
        ref={trackRef}
        className={styles.track}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        {/* Groove */}
        <div className={styles.groove} />

        {/* Tick marks */}
        {TICKS.map((t) => (
          <div key={t.label} className={styles.tick} style={{ bottom: `${t.pct}%` }} />
        ))}
        {/* Minor ticks */}
        {[13, 27, 40, 53, 67, 80, 93].map((t) => (
          <div key={t} className={styles.tickMinor} style={{ bottom: `${t}%` }} />
        ))}

        {/* Knob */}
        <div
          className={`${styles.knob} ${muted ? styles.knobMuted : ""}`}
          style={{ bottom: knobBottom }}
        >
          <div className={styles.knobCap}>
            <div className={styles.knobLine} />
          </div>
        </div>
      </div>
    </div>
  );
}
