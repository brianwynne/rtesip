import { useEffect, useState } from "react";
import { RotateCcw, Power, RefreshCw, Save, Shield } from "lucide-react";
import type { SystemStatus } from "../types";
import styles from "./SettingsPage.module.css";

interface SecurityConfig {
  firewall_enabled: boolean;
  trusted_networks: string;
  gui_password_hash: string;
}

const DEFAULT_SECURITY: SecurityConfig = {
  firewall_enabled: true,
  trusted_networks: "192.168.0.0/16\n172.16.0.0/12\n10.0.0.0/8",
  gui_password_hash: "",
};

interface SipConfig {
  username: string;
  password: string;
  registrar: string;
  realm: string;
  proxy: string;
  proxy2: string;
  transport: string;
  keying: number;
  reg_timeout: number;
  stun: string;
  stun2: string;
  codecs: string[];
}

const DEFAULT_SIP: SipConfig = {
  username: "",
  password: "",
  registrar: "",
  realm: "",
  proxy: "",
  proxy2: "",
  transport: "tls",
  keying: 2,
  reg_timeout: 600,
  stun: "",
  stun2: "",
  codecs: ["opus/48000/2", "G722/16000/1", "PCMA/8000/1", "PCMU/8000/1", "L16/48000/1"],
};

const ALL_CODECS = [
  { id: "opus/48000/2", label: "Opus 48kHz Stereo" },
  { id: "L16/48000/1", label: "L16 48kHz (Linear PCM)" },
  { id: "G722/16000/1", label: "G.722 16kHz" },
  { id: "PCMA/8000/1", label: "G.711 A-law (PCMA)" },
  { id: "PCMU/8000/1", label: "G.711 μ-law (PCMU)" },
];

export function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [sip, setSip] = useState<SipConfig>(DEFAULT_SIP);
  const [version, setVersion] = useState<Record<string, unknown> | null>(null);
  const [security, setSecurity] = useState<SecurityConfig>(DEFAULT_SECURITY);
  const [newPassword, setNewPassword] = useState("");
  const [securityDirty, setSecurityDirty] = useState(false);
  const [sipDirty, setSipDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/system/status").then((r) => r.json()).then(setStatus).catch(() => {});
    fetch("/api/sip/settings").then((r) => r.json()).then((data) => setSip({ ...DEFAULT_SIP, ...data })).catch(() => {});
    fetch("/api/update/version").then((r) => r.json()).then(setVersion).catch(() => {});
    fetch("/api/system/config").then((r) => r.json()).then((data) => {
      if (data.security) setSecurity({ ...DEFAULT_SECURITY, ...data.security });
    }).catch(() => {});
  }, []);

  const updateSip = (field: string, value: unknown) => {
    setSip((prev) => ({ ...prev, [field]: value }));
    setSipDirty(true);
  };

  const toggleCodec = (codecId: string) => {
    setSip((prev) => {
      const codecs = prev.codecs.includes(codecId)
        ? prev.codecs.filter((c) => c !== codecId)
        : [...prev.codecs, codecId];
      return { ...prev, codecs };
    });
    setSipDirty(true);
  };

  const saveSip = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/sip/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sip),
      });
      if (res.ok) setSipDirty(false);
    } catch {}
    setSaving(false);
  };

  const formatUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
  };

  return (
    <div className={styles.page}>
      <h2 className={styles.heading}>Settings</h2>

      {/* SIP Account */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3 className={styles.cardTitle}>SIP Account</h3>
          {sipDirty && (
            <button className={styles.saveBtn} onClick={saveSip} disabled={saving}>
              <Save size={12} />
              <span>{saving ? "Saving..." : "Save & Apply"}</span>
            </button>
          )}
        </div>
        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>Username</span>
            <input type="text" value={sip.username} onChange={(e) => updateSip("username", e.target.value)} placeholder="user" />
          </label>
          <label className={styles.field}>
            <span>Password</span>
            <input type="password" value={sip.password} onChange={(e) => updateSip("password", e.target.value)} placeholder="••••••" />
          </label>
          <label className={styles.field}>
            <span>Registrar</span>
            <input type="text" value={sip.registrar} onChange={(e) => updateSip("registrar", e.target.value)} placeholder="proxy.sip.audio" />
          </label>
          <label className={styles.field}>
            <span>Realm</span>
            <input type="text" value={sip.realm} onChange={(e) => updateSip("realm", e.target.value)} placeholder="sip.audio" />
          </label>
          <label className={styles.field}>
            <span>Proxy</span>
            <input type="text" value={sip.proxy} onChange={(e) => updateSip("proxy", e.target.value)} placeholder="proxy.sip.audio" />
          </label>
          <label className={styles.field}>
            <span>Proxy 2</span>
            <input type="text" value={sip.proxy2} onChange={(e) => updateSip("proxy2", e.target.value)} placeholder="proxy2.sip.audio" />
          </label>
          <label className={styles.field}>
            <span>Transport</span>
            <select value={sip.transport} onChange={(e) => updateSip("transport", e.target.value)}>
              <option value="tls">TLS</option>
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
            </select>
          </label>
          <label className={styles.field}>
            <span>Encryption</span>
            <select value={sip.keying} onChange={(e) => updateSip("keying", Number(e.target.value))}>
              <option value={0}>None</option>
              <option value={1}>SDES</option>
              <option value={2}>SDES (mandatory)</option>
            </select>
          </label>
          <label className={styles.field}>
            <span>Reg Timeout</span>
            <input type="number" value={sip.reg_timeout} onChange={(e) => updateSip("reg_timeout", Number(e.target.value))} min={60} max={3600} />
          </label>
          <label className={styles.field}>
            <span>STUN Server</span>
            <input type="text" value={sip.stun} onChange={(e) => updateSip("stun", e.target.value)} placeholder="stun.example.com" />
          </label>
          <label className={styles.field}>
            <span>STUN Server 2</span>
            <input type="text" value={sip.stun2} onChange={(e) => updateSip("stun2", e.target.value)} placeholder="stun2.example.com" />
          </label>
        </div>

      </div>

      {/* Security */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3 className={styles.cardTitle}>Security</h3>
          {securityDirty && (
            <button className={styles.saveBtn} onClick={async () => {
              setSaving(true);
              const payload: Record<string, unknown> = { ...security };
              if (newPassword) {
                const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(newPassword));
                payload.gui_password_hash = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
              }
              try {
                await fetch("/api/system/config", {
                  method: "PUT",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ security: payload }),
                });
                setSecurityDirty(false);
                setNewPassword("");
              } catch {}
              setSaving(false);
            }} disabled={saving}>
              <Save size={12} />
              <span>{saving ? "Saving..." : "Save"}</span>
            </button>
          )}
        </div>
        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>GUI Password</span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => { setNewPassword(e.target.value); setSecurityDirty(true); }}
              placeholder="Enter new password"
            />
          </label>
          <label className={styles.field}>
            <span>Firewall</span>
            <select
              value={security.firewall_enabled ? "enabled" : "disabled"}
              onChange={(e) => {
                setSecurity((prev) => ({ ...prev, firewall_enabled: e.target.value === "enabled" }));
                setSecurityDirty(true);
              }}
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </select>
          </label>
        </div>
        <div className={styles.textareaGroup}>
          <span className={styles.textareaLabel}>Trusted Networks</span>
          <textarea
            className={styles.textarea}
            value={security.trusted_networks}
            onChange={(e) => {
              setSecurity((prev) => ({ ...prev, trusted_networks: e.target.value }));
              setSecurityDirty(true);
            }}
            rows={4}
            placeholder={"192.168.0.0/16\n172.16.0.0/12\n10.0.0.0/8"}
          />
        </div>
      </div>

      {/* System info */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>System</h3>
        {status ? (
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
        ) : (
          <div className={styles.infoGrid}>
            <span className={styles.infoLabel}>Status</span>
            <span className={styles.infoValue}>Not connected</span>
          </div>
        )}
      </div>

      {/* Firmware */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Firmware</h3>
        <div className={styles.infoGrid}>
          <span className={styles.infoLabel}>Version</span>
          <span className={styles.infoValue}>{version ? String(version.version || "0.1.0") : "—"}</span>
          <span className={styles.infoLabel}>Partition</span>
          <span className={styles.infoValue}>{version ? String(version.partition || "A") : "—"}</span>
        </div>
      </div>

      {/* Actions */}
      <div className={styles.actions}>
        <button className={styles.actionBtn} onClick={() => { if (confirm("Restart services?")) fetch("/api/system/restart-services", { method: "POST" }); }}>
          <RefreshCw size={14} />
          <span>Restart Services</span>
        </button>
        <button className={styles.actionBtn} onClick={() => { if (confirm("Reboot device?")) fetch("/api/system/reboot", { method: "POST" }); }}>
          <Power size={14} />
          <span>Reboot</span>
        </button>
        <button className={styles.actionBtnDanger} onClick={() => { if (confirm("Factory reset? This will erase all settings.")) fetch("/api/system/factory-reset", { method: "POST" }); }}>
          <RotateCcw size={14} />
          <span>Factory Reset</span>
        </button>
      </div>
    </div>
  );
}
