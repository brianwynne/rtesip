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
  { pct: 83, label: "50" },
  { pct: 50, label: "25" },
  { pct: 25, label: "10" },
  { pct: 0, label: "0" },
];

/** Convert fader position (0-1) to level (0-maxLevel) using a curve.
 *  Bottom half of travel covers 0-25%, top half covers 25-100%.
 *  This gives fine control in the normal operating range (0-25%). */
function posToLevel(pos: number, max: number): number {
  if (pos <= 0.5) {
    // Bottom half: 0-50% position → 0-25% level (linear within half)
    return (pos / 0.5) * 0.25 * max;
  }
  // Top half: 50-100% position → 25-100% level
  return (0.25 + ((pos - 0.5) / 0.5) * 0.75) * max;
}

/** Inverse: convert level (0-maxLevel) to fader position (0-1). */
function levelToPos(level: number, max: number): number {
  const pct = level / max;
  if (pct <= 0.25) {
    return (pct / 0.25) * 0.5;
  }
  return 0.5 + ((pct - 0.25) / 0.75) * 0.5;
}

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
    const pos = Math.max(0, Math.min(1, 1 - (clientY - rect.top) / rect.height));
    return Math.round(posToLevel(pos, maxLevel));
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

  const pct = levelToPos(localLevel, maxLevel) * 100;
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
        {[10, 20, 30, 40, 60, 70, 90].map((t) => (
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
