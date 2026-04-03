import { useEffect, useState } from "react";
import { RotateCcw, Power, RefreshCw, Save, Search, Signal } from "lucide-react";
import type { SystemStatus } from "../types";
import styles from "./SettingsPage.module.css";

interface WifiConfig {
  enabled: boolean;
  ssid: string;
  psk: string;
  interface: string;
  country: string;
  enable_8021x: boolean;
  "8021x_user": string;
  "8021x_password": string;
  "8021x_peaplabel1": boolean;
}

const DEFAULT_WIFI: WifiConfig = {
  enabled: false,
  ssid: "",
  psk: "",
  interface: "wlan0",
  country: "ie",
  enable_8021x: false,
  "8021x_user": "",
  "8021x_password": "",
  "8021x_peaplabel1": false,
};

interface NetworkConfig {
  mode: string;
  dual_path_failover: boolean;
  hostname: string;
  address: string;
  netmask: string;
  gateway: string;
  dns1: string;
  dns2: string;
}

const DEFAULT_NETWORK: NetworkConfig = {
  mode: "dhcp",
  dual_path_failover: false,
  hostname: "sip-reporter",
  address: "",
  netmask: "",
  gateway: "",
  dns1: "",
  dns2: "",
};

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


export function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [version, setVersion] = useState<Record<string, unknown> | null>(null);
  const [security, setSecurity] = useState<SecurityConfig>(DEFAULT_SECURITY);
  const [wifi, setWifi] = useState<WifiConfig>(DEFAULT_WIFI);
  const [network, setNetwork] = useState<NetworkConfig>(DEFAULT_NETWORK);
  const [networkDirty, setNetworkDirty] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [securityDirty, setSecurityDirty] = useState(false);
  const [wifiDirty, setWifiDirty] = useState(false);
  const [wifiNetworks, setWifiNetworks] = useState<Array<{ ssid: string; signal: number; security: string }>>([]);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmAction, setConfirmAction] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/system/status").then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); }).then(setStatus).catch(() => {});
    fetch("/api/update/version").then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); }).then(setVersion).catch(() => {});
    fetch("/api/system/config").then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); }).then((data) => {
      if (data.security) setSecurity({ ...DEFAULT_SECURITY, ...data.security });
      if (data.wifi) setWifi({ ...DEFAULT_WIFI, ...data.wifi });
      if (data.network) setNetwork({ ...DEFAULT_NETWORK, ...data.network });
    }).catch(() => {});
  }, []);

  const updateNetwork = (field: string, value: unknown) => {
    setNetwork((prev) => ({ ...prev, [field]: value }));
    setNetworkDirty(true);
  };

  const saveNetwork = async () => {
    setSaving(true);
    try {
      await fetch("/api/system/network", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(network),
      });
      setNetworkDirty(false);
    } catch {}
    setSaving(false);
  };

  const updateWifi = (field: string, value: unknown) => {
    setWifi((prev) => ({ ...prev, [field]: value }));
    setWifiDirty(true);
  };

  const scanWifi = async () => {
    setScanning(true);
    try {
      const res = await fetch("/api/system/wifi/scan");
      if (res.ok) {
        const data = await res.json();
        setWifiNetworks(data.networks || []);
      }
    } catch {}
    setScanning(false);
  };

  const saveWifi = async () => {
    setSaving(true);
    try {
      await fetch("/api/system/wifi", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(wifi),
      });
      setWifiDirty(false);
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

      {/* Security */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3 className={styles.cardTitle}>Security</h3>
          {securityDirty && (
            <button className={styles.saveBtn} onClick={async () => {
              setSaving(true);
              const payload: Record<string, unknown> = { ...security };
              if (newPassword) {
                try {
                  if (typeof crypto !== "undefined" && crypto.subtle) {
                    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(newPassword));
                    payload.gui_password_hash = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
                  } else {
                    // djb2 fallback for HTTP deployments
                    let h = 5381;
                    for (let i = 0; i < newPassword.length; i++) h = ((h << 5) + h + newPassword.charCodeAt(i)) >>> 0;
                    payload.gui_password_hash = h.toString(16).padStart(8, "0");
                  }
                } catch {
                  console.error("Failed to hash password");
                  setSaving(false);
                  return;
                }
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

      {/* WiFi */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3 className={styles.cardTitle}>WiFi</h3>
          {wifiDirty && (
            <button className={styles.saveBtn} onClick={saveWifi} disabled={saving}>
              <Save size={12} />
              <span>{saving ? "Saving..." : "Save & Apply"}</span>
            </button>
          )}
        </div>
        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>WiFi</span>
            <select value={wifi.enabled ? "on" : "off"} onChange={(e) => updateWifi("enabled", e.target.value === "on")}>
              <option value="off">Off</option>
              <option value="on">On</option>
            </select>
          </label>
          <label className={styles.field}>
            <span>Interface</span>
            <select value={wifi.interface} onChange={(e) => updateWifi("interface", e.target.value)}>
              <option value="wlan0">wlan0</option>
              <option value="wlan1">wlan1</option>
            </select>
          </label>
          {wifi.enabled && (
            <>
              <label className={styles.field}>
                <span>SSID</span>
                <div className={styles.ssidRow}>
                  <input type="text" value={wifi.ssid} onChange={(e) => updateWifi("ssid", e.target.value)} placeholder="Network name" />
                  <button className={styles.scanBtn} onClick={scanWifi} disabled={scanning} title="Scan for networks">
                    <Search size={12} />
                  </button>
                </div>
              </label>
              {wifiNetworks.length > 0 && (
                <div className={styles.networkList}>
                  {wifiNetworks.map((n) => (
                    <button
                      key={n.ssid}
                      className={`${styles.networkItem} ${wifi.ssid === n.ssid ? styles.networkSelected : ""}`}
                      onClick={() => { updateWifi("ssid", n.ssid); setWifiNetworks([]); }}
                    >
                      <Signal size={12} className={n.signal > -50 ? styles.signalStrong : n.signal > -70 ? styles.signalMedium : styles.signalWeak} />
                      <span className={styles.networkSsid}>{n.ssid}</span>
                      <span className={styles.networkSecurity}>{n.security}</span>
                      <span className={styles.networkSignal}>{n.signal}dBm</span>
                    </button>
                  ))}
                </div>
              )}
              {scanning && <div className={styles.scanStatus}>Scanning...</div>}
              <label className={styles.field}>
                <span>Password</span>
                <input type="password" value={wifi.psk} onChange={(e) => updateWifi("psk", e.target.value)} placeholder="WiFi password" />
              </label>
              <label className={styles.field}>
                <span>Country</span>
                <select value={wifi.country} onChange={(e) => updateWifi("country", e.target.value)}>
                  <option value="ie">Ireland</option>
                  <option value="gb">United Kingdom</option>
                  <option value="us">United States</option>
                  <option value="de">Germany</option>
                  <option value="fr">France</option>
                  <option value="nl">Netherlands</option>
                  <option value="es">Spain</option>
                  <option value="it">Italy</option>
                  <option value="au">Australia</option>
                </select>
              </label>
            </>
          )}
        </div>

        {/* 802.1X Wired Auth */}
        {wifi.enabled && (
          <div className={styles.subSection}>
            <label className={styles.toggle}>
              <span>802.1X Wired Auth</span>
              <input
                type="checkbox"
                checked={wifi.enable_8021x}
                onChange={(e) => updateWifi("enable_8021x", e.target.checked)}
              />
            </label>
            {wifi.enable_8021x && (
              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span>Username</span>
                  <input type="text" value={wifi["8021x_user"]} onChange={(e) => updateWifi("8021x_user", e.target.value)} placeholder="802.1X identity" />
                </label>
                <label className={styles.field}>
                  <span>Password</span>
                  <input type="password" value={wifi["8021x_password"]} onChange={(e) => updateWifi("8021x_password", e.target.value)} placeholder="802.1X password" />
                </label>
                <label className={styles.toggle}>
                  <span>PEAP Label 1</span>
                  <input
                    type="checkbox"
                    checked={wifi["8021x_peaplabel1"]}
                    onChange={(e) => updateWifi("8021x_peaplabel1", e.target.checked)}
                  />
                </label>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Network */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <h3 className={styles.cardTitle}>Network</h3>
          {networkDirty && (
            <button className={styles.saveBtn} onClick={saveNetwork} disabled={saving}>
              <Save size={12} />
              <span>{saving ? "Saving..." : "Save & Apply"}</span>
            </button>
          )}
        </div>
        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>Hostname</span>
            <input type="text" value={network.hostname} onChange={(e) => updateNetwork("hostname", e.target.value)} placeholder="sip-reporter" />
          </label>
          <label className={styles.field}>
            <span>Mode</span>
            <select value={network.mode} onChange={(e) => updateNetwork("mode", e.target.value)}>
              <option value="dhcp">DHCP</option>
              <option value="static">Static IP</option>
            </select>
          </label>
          <label className={styles.toggle}>
            <span>Dual-Path Failover</span>
            <input
              type="checkbox"
              checked={network.dual_path_failover}
              onChange={(e) => updateNetwork("dual_path_failover", e.target.checked)}
            />
          </label>
          {network.dual_path_failover && (
            <div className={styles.hint}>
              Registers SIP on both ethernet and WiFi. If one interface fails,
              calls continue on the other. Requires both interfaces connected.
              Restart required to apply.
            </div>
          )}
          {network.mode === "static" && (
            <>
              <label className={styles.field}>
                <span>IP Address</span>
                <input type="text" value={network.address} onChange={(e) => updateNetwork("address", e.target.value)} placeholder="192.168.1.100" />
              </label>
              <label className={styles.field}>
                <span>Netmask</span>
                <input type="text" value={network.netmask} onChange={(e) => updateNetwork("netmask", e.target.value)} placeholder="255.255.255.0" />
              </label>
              <label className={styles.field}>
                <span>Gateway</span>
                <input type="text" value={network.gateway} onChange={(e) => updateNetwork("gateway", e.target.value)} placeholder="192.168.1.1" />
              </label>
              <label className={styles.field}>
                <span>DNS 1</span>
                <input type="text" value={network.dns1} onChange={(e) => updateNetwork("dns1", e.target.value)} placeholder="8.8.8.8" />
              </label>
              <label className={styles.field}>
                <span>DNS 2</span>
                <input type="text" value={network.dns2} onChange={(e) => updateNetwork("dns2", e.target.value)} placeholder="8.8.4.4" />
              </label>
            </>
          )}
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
        <button className={styles.actionBtn} onClick={() => {
          if (confirmAction === "restart") {
            fetch("/api/system/restart-services", { method: "POST" }).catch(() => {});
            setConfirmAction(null);
          } else {
            setConfirmAction("restart");
          }
        }}>
          <RefreshCw size={14} />
          <span>{confirmAction === "restart" ? "Confirm?" : "Restart Services"}</span>
        </button>
        <button className={styles.actionBtn} onClick={() => {
          if (confirmAction === "reboot") {
            fetch("/api/system/reboot", { method: "POST" }).catch(() => {});
            setConfirmAction(null);
          } else {
            setConfirmAction("reboot");
          }
        }}>
          <Power size={14} />
          <span>{confirmAction === "reboot" ? "Confirm?" : "Reboot"}</span>
        </button>
        <button className={styles.actionBtnDanger} onClick={() => {
          if (confirmAction === "factory") {
            fetch("/api/system/factory-reset", { method: "POST" }).catch(() => {});
            setConfirmAction(null);
          } else {
            setConfirmAction("factory");
          }
        }}>
          <RotateCcw size={14} />
          <span>{confirmAction === "factory" ? "Confirm?" : "Factory Reset"}</span>
        </button>
      </div>
    </div>
  );
}
