import { useState } from "react";
import { Lock } from "lucide-react";
import { Logo } from "./Logo";
import styles from "./LoginScreen.module.css";

interface Props {
  onLogin: (password: string) => void;
  failed: boolean;
}

export function LoginScreen({ onLogin, failed }: Props) {
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onLogin(password);
  };

  return (
    <div className={styles.screen}>
      <div className={styles.card}>
        <Logo size="large" />
        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.inputGroup}>
            <Lock size={16} className={styles.inputIcon} />
            <input
              className={styles.input}
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              autoComplete="current-password"
            />
          </div>
          {failed && <div className={styles.error}>Incorrect password</div>}
          <button className={styles.loginBtn} type="submit">
            Connect
          </button>
        </form>
      </div>
    </div>
  );
}
