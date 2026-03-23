import { useEffect, useState } from "react";
import { StatusBar } from "./components/StatusBar";
import { NavBar, type Page } from "./components/NavBar";
import { CallPage } from "./pages/CallPage";
import { AudioPage } from "./pages/AudioPage";
import { ContactsPage } from "./pages/ContactsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { useWebSocket } from "./hooks/useWebSocket";
import type { Contact } from "./types";
import styles from "./App.module.css";

function App() {
  const [page, setPage] = useState<Page>("call");
  const [contacts] = useState<Contact[]>([]);
  const [ipAddress, setIpAddress] = useState("");
  const ws = useWebSocket();

  useEffect(() => {
    fetch("/api/system/status")
      .then((r) => r.json())
      .then((data) => {
        if (data.hostname) setIpAddress(data.hostname);
      })
      .catch(() => {
        setIpAddress(window.location.hostname);
      });
  }, []);

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
          />
        )}
        {page === "audio" && <AudioPage />}
        {page === "contacts" && <ContactsPage />}
        {page === "settings" && <SettingsPage />}
      </main>
      <NavBar active={page} onChange={setPage} />
    </div>
  );
}

export default App;
