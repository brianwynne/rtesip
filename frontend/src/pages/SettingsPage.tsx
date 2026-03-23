import { useEffect, useState } from "react";
import { RotateCcw, Power, RefreshCw } from "lucide-react";
import type { SystemStatus } from "../types";
import styles from "./SettingsPage.module.css";

export function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [sipSettings, setSipSettings] = useState<Record<string, unknown> | null>(null);
  const [version, setVersion] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    fetch("/api/system/status").then((r) => r.json()).then(setStatus).catch(() => {});
    fetch("/api/sip/settings").then((r) => r.json()).then(setSipSettings).catch(() => {});
    fetch("/api/update/version").then((r) => r.json()).then(setVersion).catch(() => {});
  }, []);

  const formatUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
  };

  return (
    <div className={styles.page}>
      <h2 className={styles.heading}>Settings</h2>

      {/* System info */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>System</h3>
        {status && (
          <div className={styles.infoGrid}>
            <span className={styles.infoLabel}>Hostname</span>
            <span className={styles.infoValue}>{status.hostname}</span>
            <span className={styles.infoLabel}>CPU Temp</span>
            <span className={styles.infoValue}>{status.cpu_temp}</span>
            <span className={styles.infoLabel}>Uptime</span>
            <span className={styles.infoValue}>{formatUptime(status.uptime_seconds)}</span>
            <span className={styles.infoLabel}>Serial</span>
            <span className={styles.infoValue}>{status.serial || "—"}</span>
            <span className={styles.infoLabel}>Model</span>
            <span className={styles.infoValue}>{status.model || "—"}</span>
          </div>
        )}
      </div>

      {/* Version */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Firmware</h3>
        <div className={styles.infoGrid}>
          <span className={styles.infoLabel}>Version</span>
          <span className={styles.infoValue}>
            {version ? String(version.version || "0.1.0") : "—"}
          </span>
          <span className={styles.infoLabel}>Partition</span>
          <span className={styles.infoValue}>
            {version ? String(version.partition || "A") : "—"}
          </span>
        </div>
      </div>

      {/* SIP Account */}
      {sipSettings && (
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>SIP Account</h3>
          <div className={styles.infoGrid}>
            <span className={styles.infoLabel}>Username</span>
            <span className={styles.infoValue}>{String(sipSettings.username || "—")}</span>
            <span className={styles.infoLabel}>Registrar</span>
            <span className={styles.infoValue}>{String(sipSettings.registrar || "—")}</span>
            <span className={styles.infoLabel}>Transport</span>
            <span className={styles.infoValue}>{String(sipSettings.transport || "—").toUpperCase()}</span>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className={styles.actions}>
        <button
          className={styles.actionBtn}
          onClick={() => { if (confirm("Restart services?")) fetch("/api/system/restart-services", { method: "POST" }); }}
        >
          <RefreshCw size={16} />
          <span>Restart Services</span>
        </button>
        <button
          className={styles.actionBtn}
          onClick={() => { if (confirm("Reboot device?")) fetch("/api/system/reboot", { method: "POST" }); }}
        >
          <Power size={16} />
          <span>Reboot</span>
        </button>
        <button
          className={styles.actionBtnDanger}
          onClick={() => { if (confirm("Factory reset? This will erase all settings.")) fetch("/api/system/factory-reset", { method: "POST" }); }}
        >
          <RotateCcw size={16} />
          <span>Factory Reset</span>
        </button>
      </div>
    </div>
  );
}
