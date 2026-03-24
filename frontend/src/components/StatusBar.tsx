import { Wifi, WifiOff, Shield, ShieldOff, Sun, Moon } from "lucide-react";
import { Logo } from "./Logo";
import type { AccountStatus } from "../types";
import styles from "./StatusBar.module.css";

interface Props {
  connected: boolean;
  sipReady: boolean;
  accounts: Record<string, AccountStatus>;
  ipAddress?: string;
  theme: "dark" | "light";
  onToggleTheme: () => void;
}

export function StatusBar({ connected, sipReady, accounts, ipAddress, theme, onToggleTheme }: Props) {
  const accountList = Object.values(accounts);

  return (
    <div className={styles.bar}>
      {/* Left: branding + IP */}
      <div className={styles.left}>
        <Logo size="small" />
        {ipAddress && (
          <span className={styles.ip}>{ipAddress}</span>
        )}
      </div>

      {/* Centre: SIP accounts with live status */}
      <div className={styles.center}>
        {accountList.length > 0 ? (
          accountList.map((acc) => (
            <div key={acc.id} className={styles.account}>
              <span className={acc.registered ? styles.dotGreen : styles.dotRed} />
              <span className={styles.accountId}>{acc.id}</span>
            </div>
          ))
        ) : (
          <div className={styles.account}>
            <span className={styles.dotMuted} />
            <span className={styles.accountNone}>No accounts</span>
          </div>
        )}
      </div>

      {/* Right: theme toggle + connection indicators */}
      <div className={styles.right}>
        <button className={styles.themeToggle} onClick={onToggleTheme} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
          {theme === "dark" ? <Sun size={22} /> : <Moon size={22} />}
        </button>
        <div className={styles.indicator} title={sipReady ? "TLS Active" : "No TLS"}>
          {sipReady ? (
            <Shield size={22} className={styles.iconGreen} />
          ) : (
            <ShieldOff size={22} className={styles.iconMuted} />
          )}
        </div>
        <div className={styles.indicator} title={connected ? "Connected" : "Disconnected"}>
          {connected ? (
            <Wifi size={22} className={styles.iconGreen} />
          ) : (
            <WifiOff size={22} className={styles.iconRed} />
          )}
        </div>
      </div>
    </div>
  );
}
