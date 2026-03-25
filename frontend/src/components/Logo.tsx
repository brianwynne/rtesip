import styles from "./Logo.module.css";

interface Props {
  size?: "small" | "medium" | "large";
  showWordmark?: boolean;
}

export function Logo({ size = "medium", showWordmark = true }: Props) {
  const s = size === "small" ? 2 : size === "large" ? 2.5 : 1.6;

  return (
    <div className={styles.logo} style={{ gap: `${s * 0.3}rem` }}>
      <svg
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ width: `${s * 1.4}rem`, height: `${s * 1.4}rem` }}
      >
        {/* Outer signal wave */}
        <path
          d="M48 12C54.6 17.2 58 24.8 58 32s-3.4 14.8-10 20"
          stroke="var(--accent)"
          strokeWidth="3"
          strokeLinecap="round"
          opacity="0.4"
        />
        {/* Middle signal wave */}
        <path
          d="M44 18C48.8 21.8 52 26.6 52 32s-3.2 10.2-8 14"
          stroke="var(--accent)"
          strokeWidth="3"
          strokeLinecap="round"
          opacity="0.65"
        />
        {/* Inner signal wave */}
        <path
          d="M40 24C43.2 26.6 46 29 46 32s-2.8 5.4-6 8"
          stroke="var(--accent)"
          strokeWidth="3"
          strokeLinecap="round"
          opacity="0.9"
        />
        {/* Microphone body */}
        <rect
          x="18" y="16" width="14" height="22" rx="7"
          fill="var(--accent)"
        />
        {/* Microphone stand arc */}
        <path
          d="M14 34C14 42.8 19.4 48 25 48"
          stroke="var(--text-secondary)"
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
        />
        <path
          d="M36 34C36 42.8 30.6 48 25 48"
          stroke="var(--text-secondary)"
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
        />
        {/* Microphone stand */}
        <line
          x1="25" y1="48" x2="25" y2="56"
          stroke="var(--text-secondary)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        {/* Stand base */}
        <line
          x1="19" y1="56" x2="31" y2="56"
          stroke="var(--text-secondary)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        {/* Mic grille lines */}
        <line x1="21" y1="22" x2="29" y2="22" stroke="var(--bg-primary)" strokeWidth="1" opacity="0.3" />
        <line x1="21" y1="25" x2="29" y2="25" stroke="var(--bg-primary)" strokeWidth="1" opacity="0.3" />
        <line x1="21" y1="28" x2="29" y2="28" stroke="var(--bg-primary)" strokeWidth="1" opacity="0.3" />
        <line x1="21" y1="31" x2="29" y2="31" stroke="var(--bg-primary)" strokeWidth="1" opacity="0.3" />
      </svg>
      {showWordmark && (
        <div className={styles.wordmark} style={{ fontSize: `${s * 0.65}rem` }}>
          <span className={styles.brand}>SIP</span>
          <span className={styles.product}>Reporter</span>
        </div>
      )}
    </div>
  );
}
