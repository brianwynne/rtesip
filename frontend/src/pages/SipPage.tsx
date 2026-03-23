import { useEffect, useState } from "react";
import { Plus, Trash2, Save, ChevronDown, ChevronUp, Shield, ShieldOff } from "lucide-react";
import styles from "./SipPage.module.css";

interface SipAccount {
  username: string;
  password: string;
  registrar: string;
  realm: string;
  proxy: string;
  proxy2: string;
  transport: string;
  keying: number;
  reg_timeout: number;
}

interface SipGlobal {
  stun: string;
  stun2: string;
  log_level: number;
}

const EMPTY_ACCOUNT: SipAccount = {
  username: "",
  password: "",
  registrar: "",
  realm: "",
  proxy: "",
  proxy2: "",
  transport: "tls",
  keying: 2,
  reg_timeout: 600,
};

export function SipPage() {
  const [accounts, setAccounts] = useState<SipAccount[]>([]);
  const [global, setGlobal] = useState<SipGlobal>({ stun: "", stun2: "", log_level: 3 });
  const [expanded, setExpanded] = useState<number | null>(0);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/sip/settings")
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((data) => {
        const accs = data.accounts || [];
        // If no accounts array but has username, treat as single account (legacy)
        if (accs.length === 0 && data.username) {
          accs.push({
            username: data.username || "",
            password: data.password || "",
            registrar: data.registrar || "",
            realm: data.realm || "",
            proxy: data.proxy || "",
            proxy2: data.proxy2 || "",
            transport: data.transport || "tls",
            keying: data.keying ?? 2,
            reg_timeout: data.reg_timeout ?? 600,
          });
        }
        setAccounts(accs);
        setGlobal({
          stun: data.stun || "",
          stun2: data.stun2 || "",
          log_level: data.log_level ?? 3,
        });
      })
      .catch(() => {});
  }, []);

  const updateAccount = (index: number, field: string, value: unknown) => {
    setAccounts((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
    setDirty(true);
  };

  const addAccount = () => {
    setAccounts((prev) => [...prev, { ...EMPTY_ACCOUNT }]);
    setExpanded(accounts.length);
    setDirty(true);
  };

  const removeAccount = (index: number) => {
    setAccounts((prev) => prev.filter((_, i) => i !== index));
    setExpanded(null);
    setDirty(true);
  };

  const updateGlobal = (field: string, value: unknown) => {
    setGlobal((prev) => ({ ...prev, [field]: value }));
    setDirty(true);
  };

  const saveAll = async () => {
    setSaving(true);
    try {
      await fetch("/api/sip/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          accounts,
          stun: global.stun,
          stun2: global.stun2,
          log_level: global.log_level,
        }),
      });
      setDirty(false);
    } catch {}
    setSaving(false);
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h2 className={styles.heading}>SIP Accounts</h2>
        {dirty && (
          <button className={styles.saveBtn} onClick={saveAll} disabled={saving}>
            <Save size={12} />
            <span>{saving ? "Saving..." : "Save & Apply"}</span>
          </button>
        )}
      </div>

      {/* Accounts */}
      <div className={styles.accountList}>
        {accounts.map((acc, i) => (
          <div key={i} className={styles.accountCard}>
            <button
              className={styles.accountHeader}
              onClick={() => setExpanded(expanded === i ? null : i)}
            >
              <div className={styles.accountSummary}>
                <span className={styles.accountIndex}>{i + 1}</span>
                {acc.transport === "tls" ? (
                  <Shield size={12} className={styles.iconGreen} />
                ) : (
                  <ShieldOff size={12} className={styles.iconMuted} />
                )}
                <span className={styles.accountName}>
                  {acc.username ? `${acc.username}@${acc.realm || acc.registrar}` : "New Account"}
                </span>
                <span className={styles.accountTransport}>{acc.transport.toUpperCase()}</span>
              </div>
              {expanded === i ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>

            {expanded === i && (
              <div className={styles.accountBody}>
                <div className={styles.formGrid}>
                  <label className={styles.field}>
                    <span>Username</span>
                    <input type="text" value={acc.username} onChange={(e) => updateAccount(i, "username", e.target.value)} placeholder="user" />
                  </label>
                  <label className={styles.field}>
                    <span>Password</span>
                    <input type="password" value={acc.password} onChange={(e) => updateAccount(i, "password", e.target.value)} placeholder="••••••" />
                  </label>
                  <label className={styles.field}>
                    <span>Registrar</span>
                    <input type="text" value={acc.registrar} onChange={(e) => updateAccount(i, "registrar", e.target.value)} placeholder="sip.rtegroup.ie" />
                  </label>
                  <label className={styles.field}>
                    <span>Realm</span>
                    <input type="text" value={acc.realm} onChange={(e) => updateAccount(i, "realm", e.target.value)} placeholder="sip.rtegroup.ie" />
                  </label>
                  <label className={styles.field}>
                    <span>Proxy</span>
                    <input type="text" value={acc.proxy} onChange={(e) => updateAccount(i, "proxy", e.target.value)} placeholder="sip.rtegroup.ie" />
                  </label>
                  <label className={styles.field}>
                    <span>Proxy 2</span>
                    <input type="text" value={acc.proxy2} onChange={(e) => updateAccount(i, "proxy2", e.target.value)} placeholder="sip1.rtegroup.ie" />
                  </label>
                  <label className={styles.field}>
                    <span>Transport</span>
                    <select value={acc.transport} onChange={(e) => updateAccount(i, "transport", e.target.value)}>
                      <option value="tls">TLS</option>
                      <option value="tcp">TCP</option>
                      <option value="udp">UDP</option>
                    </select>
                  </label>
                  <label className={styles.field}>
                    <span>Encryption</span>
                    <select value={acc.keying} onChange={(e) => updateAccount(i, "keying", Number(e.target.value))}>
                      <option value={0}>None</option>
                      <option value={1}>SDES</option>
                      <option value={2}>SDES (mandatory)</option>
                    </select>
                  </label>
                  <label className={styles.field}>
                    <span>Reg Timeout</span>
                    <div className={styles.fieldWithUnit}>
                      <input type="number" value={acc.reg_timeout} onChange={(e) => updateAccount(i, "reg_timeout", Number(e.target.value))} min={60} max={3600} />
                      <span className={styles.unit}>sec</span>
                    </div>
                  </label>
                </div>
                <button className={styles.removeBtn} onClick={() => removeAccount(i)}>
                  <Trash2 size={12} />
                  <span>Remove Account</span>
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <button className={styles.addBtn} onClick={addAccount}>
        <Plus size={14} />
        <span>Add Account</span>
      </button>

      {/* Global SIP settings */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Global</h3>
        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span>STUN Server</span>
            <input type="text" value={global.stun} onChange={(e) => updateGlobal("stun", e.target.value)} placeholder="stun.example.com" />
          </label>
          <label className={styles.field}>
            <span>STUN Server 2</span>
            <input type="text" value={global.stun2} onChange={(e) => updateGlobal("stun2", e.target.value)} placeholder="stun2.example.com" />
          </label>
          <label className={styles.field}>
            <span>Log Level</span>
            <select value={global.log_level} onChange={(e) => updateGlobal("log_level", Number(e.target.value))}>
              <option value={0}>0 — Fatal only</option>
              <option value={1}>1 — Errors</option>
              <option value={2}>2 — Warnings</option>
              <option value={3}>3 — Info (default)</option>
              <option value={4}>4 — Debug</option>
              <option value={5}>5 — Trace</option>
            </select>
          </label>
        </div>
      </div>
    </div>
  );
}
