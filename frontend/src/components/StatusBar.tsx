import { Globe, Shield, ShieldOff, Sun, Moon, Cable, Wifi, WifiLow, WifiOff } from "lucide-react";
import { Logo } from "./Logo";
import type { AccountStatus, CallState } from "../types";
import styles from "./StatusBar.module.css";

interface Props {
  connected: boolean;
  sipReady: boolean;
  serverReachable: boolean;
  accounts: Record<string, AccountStatus>;
  ipAddresses: Record<string, string>;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  callState: CallState;
  wifiSignal: number | null;
  publicIp: string | null;
}

export function StatusBar({ serverReachable, accounts, ipAddresses, theme, onToggleTheme, callState, wifiSignal, publicIp }: Props) {
  const accountList = Object.values(accounts);
  const hasWifi = "wlan0" in ipAddresses;
  const WifiIcon = wifiSignal == null || !hasWifi ? WifiOff : wifiSignal > -50 ? Wifi : wifiSignal > -70 ? WifiLow : WifiOff;
  const wifiColor = wifiSignal == null || !hasWifi ? styles.iconMuted : wifiSignal > -50 ? styles.iconGreen : wifiSignal > -70 ? styles.iconAmber : styles.iconRed;
  const wifiLabel = wifiSignal != null ? `WiFi ${wifiSignal} dBm` : "No WiFi";

  return (
    <div className={styles.bar}>
      {/* Left: branding + IP */}
      <div className={styles.left}>
        <Logo size="small" />
        {Object.entries(ipAddresses).map(([iface, ip]) => (
          <span key={iface} className={styles.ip}>
            {iface.startsWith("wlan") ? <Wifi size={14} /> : <Cable size={14} />}
            {ip}
          </span>
        ))}
        {publicIp && (
          <span className={styles.ip} title="Public IP">
            <Globe size={14} />
            {publicIp}
          </span>
        )}
      </div>

      {/* Spacer pushes right section to the edge */}
      <div className={styles.spacer} />

      {/* Right: accounts + theme toggle + connection indicators */}
      <div className={styles.right}>
        <div className={styles.accounts}>
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
        <button className={styles.themeToggle} onClick={onToggleTheme} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
          {theme === "dark" ? <Sun size={22} /> : <Moon size={22} />}
        </button>
        {callState.state === "connected" && (
          <div className={styles.indicator} title={callState.srtpActive ? `SRTP Active — ${callState.srtpSuite || ""}` : "SRTP Inactive"}>
            {callState.srtpActive ? (
              <Shield size={22} className={styles.iconGreen} />
            ) : (
              <ShieldOff size={22} className={styles.iconRed} />
            )}
          </div>
        )}
        {hasWifi && (
          <div className={styles.indicator} title={wifiLabel}>
            <WifiIcon size={22} className={wifiColor} />
          </div>
        )}
        <div className={styles.indicator} title={serverReachable ? "SIP Server Reachable" : "SIP Server Unreachable"}>
          <Globe size={22} className={serverReachable ? styles.iconGreen : styles.iconRed} />
        </div>
      </div>
    </div>
  );
}
