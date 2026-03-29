import { useCallback, useEffect, useState } from "react";
import { StatusBar } from "./components/StatusBar";
import { LoginScreen } from "./components/LoginScreen";
import { NavBar, type Page } from "./components/NavBar";
import { CallPage } from "./pages/CallPage";
import { AudioPage } from "./pages/AudioPage";
import { ContactsPage } from "./pages/ContactsPage";
import { WifiPage } from "./pages/WifiPage";
import { SipPage } from "./pages/SipPage";
import { SettingsPage } from "./pages/SettingsPage";
import { useWebSocket } from "./hooks/useWebSocket";
import { useRingtone } from "./hooks/useRingtone";
import { useTheme } from "./hooks/useTheme";
import type { Contact } from "./types";
import styles from "./App.module.css";

function App() {
  const [page, setPage] = useState<Page>("call");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [ipAddresses, setIpAddresses] = useState<Record<string, string>>({});
  const [wifiSignal, setWifiSignal] = useState<number | null>(null);
  const ws = useWebSocket();
  const { theme, toggle: toggleTheme } = useTheme();
  useRingtone(ws.callState.state === "incoming");

  const fetchContacts = useCallback(() => {
    fetch("/api/contacts/")
      .then((r) => (r.ok ? r.json() : []))
      .then((data: Contact[]) => setContacts(data))
      .catch(() => setContacts([]));
  }, []);

  // Load contacts on mount
  useEffect(() => {
    fetchContacts();
  }, [fetchContacts]);

  // Re-fetch contacts when switching to call tab (picks up edits from Contacts page)
  useEffect(() => {
    if (page === "call") fetchContacts();
  }, [page, fetchContacts]);

  useEffect(() => {
    const fetchStatus = () => {
      fetch("/api/system/status")
        .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
        .then((data) => {
          const ips = data.ip_addresses || {};
          if (Object.keys(ips).length > 0) {
            setIpAddresses(ips);
          } else {
            setIpAddresses({ eth0: window.location.hostname });
          }
          if (data.wifi_signal != null) setWifiSignal(data.wifi_signal);
        })
        .catch(() => {
          setIpAddresses({ eth0: window.location.hostname });
        });
    };
    fetchStatus();
    const t = setInterval(fetchStatus, 30000);
    return () => clearInterval(t);
  }, []);

  // Kiosk mode: local touchscreen only shows Call + Contacts (no Audio/Settings)
  // Triggered by ?kiosk=1 in URL (set by Cage launcher) or local access
  const isKiosk = new URLSearchParams(window.location.search).has("kiosk");

  // Hide cursor in kiosk mode (touchscreen only)
  useEffect(() => {
    if (isKiosk) {
      document.documentElement.style.cursor = "none";
      document.body.style.cursor = "none";
    }
  }, [isKiosk]);
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1" || host.startsWith("192.168.") || host.startsWith("10.") || host.startsWith("172.");

  // Skip login on local/LAN access and kiosk mode
  // Login required only for public/external access
  if (!ws.authed && !isLocal && !isKiosk) {
    return <LoginScreen onLogin={ws.authenticate} failed={ws.authFailed} />;
  }

  const isIncoming = ws.callState.state === "incoming";

  return (
    <div className={`${styles.app} ${isIncoming ? styles.appIncoming : ""}`}>
      <StatusBar
        connected={ws.connected}
        sipReady={ws.sipReady}
        serverReachable={ws.serverReachable}
        accounts={ws.accounts}
        ipAddresses={ipAddresses}
        theme={theme}
        onToggleTheme={toggleTheme}
        callState={ws.callState}
        wifiSignal={wifiSignal}
      />
      <main className={styles.content}>
        {page === "call" && (
          <CallPage
            callState={ws.callState}
            volume={ws.volume}
            contacts={contacts}
            onCall={ws.call}
            onHangup={ws.hangup}
            onAnswer={ws.answer}
            onReject={ws.reject}
            onMuteVol={() => ws.mute("vol")}
            onMuteGain={() => ws.mute("gain")}
            onLinkVol={(l) => ws.toggleLink("vol", l)}
            onSetVolLevel={ws.setVolLevel}
            onSetGainLevel={ws.setGainLevel}
            sipReady={ws.sipReady}
          />
        )}
        {page === "audio" && <AudioPage />}
        {page === "sip" && <SipPage />}
        {page === "contacts" && <ContactsPage />}
        {page === "wifi" && <WifiPage />}
        {page === "settings" && <SettingsPage />}
      </main>
      <NavBar active={page} onChange={setPage} kioskMode={isKiosk} />
    </div>
  );
}

export default App;
