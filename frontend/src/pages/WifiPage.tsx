import { useState, useEffect } from "react";
import { Wifi, WifiOff, Lock, Unlock, RefreshCw, Check } from "lucide-react";
import styles from "./WifiPage.module.css";

interface Network {
  ssid: string;
  signal: number;
  security: string;
  bssid: string;
}

export function WifiPage() {
  const [networks, setNetworks] = useState<Network[]>([]);
  const [scanning, setScanning] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState<string | null>(null);
  const [error, setError] = useState("");

  const scan = async () => {
    setScanning(true);
    setError("");
    try {
      const r = await fetch("/api/system/wifi/scan");
      const data = await r.json();
      setNetworks(data.networks || []);
    } catch {
      setError("Scan failed");
    }
    setScanning(false);
  };

  const connect = async () => {
    if (!selected) return;
    setConnecting(true);
    setError("");
    try {
      const net = networks.find((n) => n.ssid === selected);
      const isOpen = net?.security === "Open";
      await fetch("/api/system/wifi", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: true,
          ssid: selected,
          psk: isOpen ? "" : password,
        }),
      });
      setConnected(selected);
      setSelected(null);
      setPassword("");
    } catch {
      setError("Connection failed");
    }
    setConnecting(false);
  };

  const disconnect = async () => {
    try {
      await fetch("/api/system/wifi", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: false, ssid: "" }),
      });
      setConnected(null);
    } catch {
      setError("Disconnect failed");
    }
  };

  // Check current connection on load
  useEffect(() => {
    fetch("/api/system/status")
      .then((r) => r.json())
      .then((data) => {
        if (data.ip_addresses?.wlan0) {
          // WiFi is connected — get SSID
          fetch("/api/system/wifi")
            .then((r) => r.json())
            .then((wifi) => {
              if (wifi.ssid) setConnected(wifi.ssid);
            });
        }
      })
      .catch(() => {});
    scan();
  }, []);

  const signalBars = (signal: number) => {
    if (signal > 75) return 4;
    if (signal > 50) return 3;
    if (signal > 25) return 2;
    return 1;
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h2 className={styles.title}>
          <Wifi size={28} />
          WiFi
        </h2>
        <button className={styles.scanBtn} onClick={scan} disabled={scanning}>
          <RefreshCw size={22} className={scanning ? styles.spinning : ""} />
          {scanning ? "Scanning..." : "Scan"}
        </button>
      </div>

      {connected && (
        <div className={styles.connectedBanner}>
          <Check size={22} />
          <span>Connected to <strong>{connected}</strong></span>
          <button className={styles.disconnectBtn} onClick={disconnect}>Disconnect</button>
        </div>
      )}

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.list}>
        {networks.map((net) => (
          <button
            key={net.bssid}
            className={`${styles.network} ${selected === net.ssid ? styles.networkSelected : ""} ${connected === net.ssid ? styles.networkConnected : ""}`}
            onClick={() => {
              if (connected === net.ssid) return;
              setSelected(selected === net.ssid ? null : net.ssid);
              setPassword("");
            }}
          >
            <div className={styles.signalBars} data-bars={signalBars(net.signal)}>
              <div /><div /><div /><div />
            </div>
            <div className={styles.netInfo}>
              <span className={styles.ssid}>{net.ssid}</span>
              <span className={styles.security}>
                {net.security !== "Open" ? <Lock size={12} /> : <Unlock size={12} />}
                {net.security}
              </span>
            </div>
            {connected === net.ssid && <Check size={22} className={styles.checkIcon} />}
          </button>
        ))}
        {!scanning && networks.length === 0 && (
          <div className={styles.empty}>
            <WifiOff size={32} />
            <span>No networks found</span>
          </div>
        )}
      </div>

      {selected && connected !== selected && (
        <div className={styles.connectForm}>
          {networks.find((n) => n.ssid === selected)?.security !== "Open" && (
            <input
              className={styles.passwordInput}
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && connect()}
              autoFocus
            />
          )}
          <button
            className={styles.connectBtn}
            onClick={connect}
            disabled={connecting || (!password && networks.find((n) => n.ssid === selected)?.security !== "Open")}
          >
            {connecting ? "Connecting..." : `Connect to ${selected}`}
          </button>
        </div>
      )}
    </div>
  );
}
