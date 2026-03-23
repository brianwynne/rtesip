import styles from "./Meter.module.css";

interface Props {
  label: string;
  level: number;
  maxLevel?: number;
  muted?: boolean;
  vertical?: boolean;
}

export function Meter({ label, level, maxLevel = 150, muted, vertical }: Props) {
  const pct = Math.min(100, (level / maxLevel) * 100);

  // Broadcast-standard color thresholds
  const getColor = (pct: number) => {
    if (pct > 85) return "var(--meter-red)";
    if (pct > 65) return "var(--meter-yellow)";
    return "var(--meter-green)";
  };

  // Generate tick marks at standard broadcast levels
  const ticks = vertical
    ? [0, 20, 40, 60, 80, 100]
    : [0, 25, 50, 75, 100];

  return (
    <div className={`${styles.meter} ${vertical ? styles.vertical : styles.horizontal}`}>
      <span className={`${styles.label} ${muted ? styles.muted : ""}`}>{label}</span>
      <div className={styles.track}>
        <div
          className={styles.fill}
          style={{
            [vertical ? "height" : "width"]: `${pct}%`,
            background: muted
              ? "var(--text-muted)"
              : `linear-gradient(${vertical ? "to top" : "to right"}, var(--meter-green), ${getColor(pct)})`,
          }}
        />
        {ticks.map((t) => (
          <div
            key={t}
            className={styles.tick}
            style={{ [vertical ? "bottom" : "left"]: `${t}%` }}
          />
        ))}
      </div>
      <span className={styles.value}>{level}%</span>
    </div>
  );
}
