import { useState } from "react";
import { Phone, Sliders, Settings, Users, Radio, Wifi, Power, PowerOff } from "lucide-react";
import styles from "./NavBar.module.css";

export type Page = "call" | "audio" | "sip" | "contacts" | "settings" | "wifi";

interface Props {
  active: Page;
  onChange: (page: Page) => void;
  kioskMode?: boolean;
}

const allTabs: { id: Page; label: string; icon: typeof Phone; kiosk: boolean; color: string }[] = [
  { id: "call", label: "Call", icon: Phone, kiosk: true, color: "var(--green)" },
  { id: "audio", label: "Audio", icon: Sliders, kiosk: false, color: "var(--cyan)" },
  { id: "sip", label: "SIP", icon: Radio, kiosk: false, color: "var(--accent)" },
  { id: "contacts", label: "Contacts", icon: Users, kiosk: true, color: "var(--amber)" },
  { id: "wifi", label: "WiFi", icon: Wifi, kiosk: true, color: "var(--cyan)" },
  { id: "settings", label: "Settings", icon: Settings, kiosk: false, color: "var(--text-secondary)" },
];

export function NavBar({ active, onChange, kioskMode }: Props) {
  const [showPower, setShowPower] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const tabs = kioskMode ? allTabs.filter((t) => t.kiosk) : allTabs;

  const handlePowerAction = async (action: string, endpoint: string) => {
    if (confirming !== action) {
      setConfirming(action);
      return;
    }
    try {
      await fetch(`/api/system/${endpoint}`, { method: "POST" });
    } catch {
      // ignore — device will restart/shutdown
    }
    setShowPower(false);
    setConfirming(null);
  };

  return (
    <>
      <nav className={styles.nav}>
        {tabs.map(({ id, label, icon: Icon, color }) => (
          <button
            key={id}
            className={`${styles.tab} ${active === id ? styles.active : ""}`}
            style={active === id ? { color, "--tab-accent": color } as React.CSSProperties : undefined}
            onClick={() => onChange(id)}
          >
            <Icon size={28} />
            <span>{label}</span>
          </button>
        ))}
        <button
          className={`${styles.tab} ${styles.powerTab}`}
          onClick={() => { setShowPower(!showPower); setConfirming(null); }}
        >
          <Power size={28} />
        </button>
      </nav>

      {showPower && (
        <div className={styles.powerOverlay} onClick={() => { setShowPower(false); setConfirming(null); }}>
          <div className={styles.powerMenu} onClick={(e) => e.stopPropagation()}>
            <button
              className={styles.powerOption}
              onClick={() => handlePowerAction("reboot", "reboot")}
            >
              <Power size={36} />
              <span>{confirming === "reboot" ? "Tap again to confirm" : "Restart Device"}</span>
            </button>
            <button
              className={`${styles.powerOption} ${styles.powerDanger}`}
              onClick={() => handlePowerAction("shutdown", "shutdown")}
            >
              <PowerOff size={36} />
              <span>{confirming === "shutdown" ? "Tap again to confirm" : "Shut Down"}</span>
            </button>
            <button
              className={styles.powerCancel}
              onClick={() => { setShowPower(false); setConfirming(null); }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </>
  );
}
