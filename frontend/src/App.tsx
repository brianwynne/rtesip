import { useCallback, useEffect, useState } from "react";
import { StatusBar } from "./components/StatusBar";
import { LoginScreen } from "./components/LoginScreen";
import { NavBar, type Page } from "./components/NavBar";
import { CallPage } from "./pages/CallPage";
import { AudioPage } from "./pages/AudioPage";
import { ContactsPage } from "./pages/ContactsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { useWebSocket } from "./hooks/useWebSocket";
import { useRingtone } from "./hooks/useRingtone";
import type { Contact } from "./types";
import styles from "./App.module.css";

function App() {
  const [page, setPage] = useState<Page>("call");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [ipAddress, setIpAddress] = useState("");
  const ws = useWebSocket();
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
    fetch("/api/system/status")
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((data) => {
        if (data.hostname) setIpAddress(data.hostname);
      })
      .catch(() => {
        setIpAddress(window.location.hostname);
      });
  }, []);

  // Kiosk mode: local touchscreen only shows Call + Contacts (no Audio/Settings)
  // Triggered by ?kiosk=1 in URL (set by Cage launcher) or local access
  const isKiosk = new URLSearchParams(window.location.search).has("kiosk");
  const isDev = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

  // Skip login on localhost (dev) and kiosk (local touchscreen)
  if (!ws.authed && !isDev && !isKiosk) {
    return <LoginScreen onLogin={ws.authenticate} failed={ws.authFailed} />;
  }

  return (
    <div className={styles.app}>
      <StatusBar
        connected={ws.connected}
        sipReady={ws.sipReady}
        accounts={ws.accounts}
        ipAddress={ipAddress || window.location.hostname}
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
            onVolUp={(ch) => ws.setVol(ch, "up")}
            onVolDown={(ch) => ws.setVol(ch, "down")}
            onGainUp={(ch) => ws.setGain(ch, "up")}
            onGainDown={(ch) => ws.setGain(ch, "down")}
            onMuteVol={() => ws.mute("vol")}
            onMuteGain={() => ws.mute("gain")}
            onLinkVol={(l) => ws.toggleLink("vol", l)}
            onLinkGain={(l) => ws.toggleLink("gain", l)}
            onSetVolLevel={ws.setVolLevel}
            onSetGainLevel={ws.setGainLevel}
            sipReady={ws.sipReady}
          />
        )}
        {page === "audio" && <AudioPage />}
        {page === "contacts" && <ContactsPage />}
        {page === "settings" && <SettingsPage />}
      </main>
      <NavBar active={page} onChange={setPage} kioskMode={isKiosk} />
    </div>
  );
}

export default App;
