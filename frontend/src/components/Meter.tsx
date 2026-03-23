import styles from "./Meter.module.css";

interface Props {
  label: string;
  level: number;
  maxLevel?: number;
  muted?: boolean;
  vertical?: boolean;
  scalePosition?: "left" | "right" | "none";
}

const TICKS = [
  { pct: 100, label: "+12" },
  { pct: 87, label: "0" },
  { pct: 67, label: "-12" },
  { pct: 47, label: "-24" },
  { pct: 27, label: "-36" },
  { pct: 0, label: "-48" },
];

export function Meter({ label, level, maxLevel = 150, muted, vertical, scalePosition = "none" }: Props) {
  const pct = Math.min(100, (level / maxLevel) * 100);

  if (vertical) {
    const scaleLeft = scalePosition === "left";
    const scaleRight = scalePosition === "right";

    return (
      <div className={styles.vertical}>
        <div className={styles.meterRow}>
          {scaleLeft && (
            <div className={styles.scale}>
              {TICKS.map((t) => (
                <div key={t.label} className={`${styles.tickLabel} ${styles.tickRight}`} style={{ bottom: `${t.pct}%` }}>
                  {t.label}
                </div>
              ))}
            </div>
          )}
          <div className={styles.trackVertical}>
            <div
              className={styles.fillVertical}
              style={{
                height: `${pct}%`,
                background: muted ? "var(--text-muted)" : undefined,
              }}
            />
            {Array.from({ length: 24 }).map((_, i) => (
              <div
                key={i}
                className={styles.segment}
                style={{ bottom: `${(i / 24) * 100}%` }}
              />
            ))}
          </div>
          {scaleRight && (
            <div className={styles.scale}>
              {TICKS.map((t) => (
                <div key={t.label} className={`${styles.tickLabel} ${styles.tickLeft}`} style={{ bottom: `${t.pct}%` }}>
                  {t.label}
                </div>
              ))}
            </div>
          )}
        </div>
        <span className={`${styles.chLabel} ${muted ? styles.chMuted : ""}`}>{label}</span>
      </div>
    );
  }

  // Horizontal fallback
  const getGradient = () => {
    if (muted) return "var(--text-muted)";
    return `linear-gradient(to right, var(--meter-green) 0%, var(--meter-green) 60%, var(--meter-yellow) 80%, var(--meter-red) 100%)`;
  };

  return (
    <div className={styles.horizontal}>
      <span className={styles.chLabel}>{label}</span>
      <div className={styles.trackHorizontal}>
        <div
          className={styles.fillHorizontal}
          style={{ width: `${pct}%`, background: getGradient() }}
        />
      </div>
      <span className={styles.value}>{level}%</span>
    </div>
  );
}
