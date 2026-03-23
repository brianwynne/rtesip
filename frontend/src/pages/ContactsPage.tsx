import { useEffect, useState } from "react";
import { Plus, Trash2, Star, StarOff } from "lucide-react";
import type { Contact } from "../types";
import styles from "./ContactsPage.module.css";

export function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [draft, setDraft] = useState({ name: "", address: "", type: "sip" as Contact["type"] });

  const load = () => {
    fetch("/api/contacts/")
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setContacts)
      .catch(() => {});
  };

  useEffect(load, []);

  const addContact = async () => {
    try {
      const res = await fetch("/api/contacts/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...draft, quickDial: false }),
      });
      if (res.ok) {
        load();
        setDraft({ name: "", address: "", type: "sip" });
      }
    } catch {
      // network error
    }
  };

  const deleteContact = async (id: number) => {
    try {
      await fetch(`/api/contacts/${id}`, { method: "DELETE" });
    } catch {
      // network error
    }
    load();
  };

  const toggleQuickDial = async (contact: Contact) => {
    try {
      await fetch(`/api/contacts/${contact.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...contact, quickDial: !contact.quickDial }),
      });
    } catch {
      // network error
    }
    load();
  };

  return (
    <div className={styles.page}>
      <h2 className={styles.heading}>Contacts</h2>

      {/* Add contact */}
      <div className={styles.addRow}>
        <input
          className={styles.addInput}
          placeholder="Name"
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        />
        <input
          className={styles.addInput}
          placeholder="SIP Address"
          value={draft.address}
          onChange={(e) => setDraft({ ...draft, address: e.target.value })}
        />
        <button
          className={styles.addBtn}
          onClick={addContact}
          disabled={!draft.name || !draft.address}
        >
          <Plus size={16} />
        </button>
      </div>

      {/* Contact list */}
      <div className={styles.list}>
        {contacts.map((c) => (
          <div key={c.id} className={styles.item}>
            <button
              className={`${styles.starBtn} ${c.quickDial ? styles.starred : ""}`}
              onClick={() => toggleQuickDial(c)}
              title={c.quickDial ? "Remove from quick dial" : "Add to quick dial"}
            >
              {c.quickDial ? <Star size={14} /> : <StarOff size={14} />}
            </button>
            <div className={styles.info}>
              <span className={styles.name}>{c.name}</span>
              <span className={styles.address}>{c.address}</span>
            </div>
            <span className={styles.typeBadge}>{c.type}</span>
            <button className={styles.deleteBtn} onClick={() => deleteContact(c.id)}>
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {contacts.length === 0 && (
          <div className={styles.empty}>No contacts. Add one above.</div>
        )}
      </div>
    </div>
  );
}
