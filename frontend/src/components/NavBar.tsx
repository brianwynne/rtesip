import { Phone, Sliders, Settings, Users } from "lucide-react";
import styles from "./NavBar.module.css";

export type Page = "call" | "audio" | "contacts" | "settings";

interface Props {
  active: Page;
  onChange: (page: Page) => void;
}

const tabs: { id: Page; label: string; icon: typeof Phone }[] = [
  { id: "call", label: "Call", icon: Phone },
  { id: "audio", label: "Audio", icon: Sliders },
  { id: "contacts", label: "Contacts", icon: Users },
  { id: "settings", label: "Settings", icon: Settings },
];

export function NavBar({ active, onChange }: Props) {
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
