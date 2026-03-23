import { Wifi, WifiOff, Phone, PhoneOff, Shield, ShieldOff } from "lucide-react";
import type { AccountStatus } from "../types";
import styles from "./StatusBar.module.css";

interface Props {
  connected: boolean;
  sipReady: boolean;
  accounts: Record<string, AccountStatus>;
  hostname?: string;
}

export function StatusBar({ connected, sipReady, accounts, hostname }: Props) {
  const registeredCount = Object.values(accounts).filter((a) => a.registered).length;
  const totalCount = Object.keys(accounts).length;

  return (
    <div className={styles.bar}>
      <div className={styles.left}>
        <span className={styles.brand}>RTE</span>
        <span className={styles.product}>SIP</span>
        {hostname && <span className={styles.hostname}>{hostname}</span>}
      </div>
      <div className={styles.right}>
        {totalCount > 0 && (
          <div className={styles.indicator} title={`${registeredCount}/${totalCount} accounts registered`}>
            {sipReady ? (
              <Phone size={14} className={styles.iconGreen} />
            ) : (
              <PhoneOff size={14} className={styles.iconRed} />
            )}
            <span className={sipReady ? styles.textGreen : styles.textRed}>
              {registeredCount}/{totalCount}
            </span>
          </div>
        )}
        <div className={styles.indicator} title={sipReady ? "TLS Active" : "No TLS"}>
          {sipReady ? (
            <Shield size={14} className={styles.iconGreen} />
          ) : (
            <ShieldOff size={14} className={styles.iconMuted} />
          )}
        </div>
        <div className={styles.indicator} title={connected ? "Connected" : "Disconnected"}>
          {connected ? (
            <Wifi size={14} className={styles.iconGreen} />
          ) : (
            <WifiOff size={14} className={styles.iconRed} />
          )}
        </div>
      </div>
    </div>
  );
}
