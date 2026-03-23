import { Phone, Sliders, Settings, Users, Radio } from "lucide-react";
import styles from "./NavBar.module.css";

export type Page = "call" | "audio" | "sip" | "contacts" | "settings";

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
  { id: "settings", label: "Settings", icon: Settings, kiosk: false, color: "var(--text-secondary)" },
];

export function NavBar({ active, onChange, kioskMode }: Props) {
  const tabs = kioskMode ? allTabs.filter((t) => t.kiosk) : allTabs;

  return (
    <nav className={styles.nav}>
      {tabs.map(({ id, label, icon: Icon, color }) => (
        <button
          key={id}
          className={`${styles.tab} ${active === id ? styles.active : ""}`}
          style={active === id ? { color, "--tab-accent": color } as React.CSSProperties : undefined}
          onClick={() => onChange(id)}
        >
          <Icon size={18} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
