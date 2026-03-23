import { Phone, Sliders, Settings, Users } from "lucide-react";
import styles from "./NavBar.module.css";

export type Page = "call" | "audio" | "contacts" | "settings";

interface Props {
  active: Page;
  onChange: (page: Page) => void;
  kioskMode?: boolean;
}

const allTabs: { id: Page; label: string; icon: typeof Phone; kiosk: boolean }[] = [
  { id: "call", label: "Call", icon: Phone, kiosk: true },
  { id: "audio", label: "Audio", icon: Sliders, kiosk: false },
  { id: "contacts", label: "Contacts", icon: Users, kiosk: true },
  { id: "settings", label: "Settings", icon: Settings, kiosk: false },
];

export function NavBar({ active, onChange, kioskMode }: Props) {
  const tabs = kioskMode ? allTabs.filter((t) => t.kiosk) : allTabs;

  return (
    <nav className={styles.nav}>
      {tabs.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          className={`${styles.tab} ${active === id ? styles.active : ""}`}
          onClick={() => onChange(id)}
        >
          <Icon size={18} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
