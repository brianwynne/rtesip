import { useEffect, useState } from "react";
import styles from "./AudioPage.module.css";

interface AudioSettings {
  channels: number;
  bitrate: number;
  input: string;
  output: string;
  input_routing: string;
  output_routing: string;
  capture_latency: number;
  playback_latency: number;
  period_size: number;
  auto_answer: boolean;
  hardware_mixer: boolean;
  phantom_power: boolean;
}

export function AudioPage() {
  const [settings, setSettings] = useState<AudioSettings | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/audio/settings")
      .then((r) => r.json())
      .then(setSettings)
      .catch(() => {});
  }, []);

  const save = async (updates: Partial<AudioSettings>) => {
    setSaving(true);
    const res = await fetch("/api/audio/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (res.ok) setSettings(await res.json());
    setSaving(false);
  };

  if (!settings) return <div className={styles.page}><div className={styles.loading}>Loading...</div></div>;

  return (
    <div className={styles.page}>
      <h2 className={styles.heading}>Audio Configuration</h2>

      <div className={styles.grid}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>General</h3>
          <label className={styles.field}>
            <span>Channels</span>
            <select
              value={settings.channels}
              onChange={(e) => save({ channels: Number(e.target.value) })}
            >
              <option value={1}>Mono</option>
              <option value={2}>Stereo</option>
            </select>
          </label>
          <label className={styles.field}>
            <span>Bitrate</span>
            <select
              value={settings.bitrate}
              onChange={(e) => save({ bitrate: Number(e.target.value) })}
            >
              <option value={32000}>32 kbps</option>
              <option value={48000}>48 kbps</option>
              <option value={64000}>64 kbps</option>
              <option value={72000}>72 kbps</option>
              <option value={96000}>96 kbps</option>
              <option value={128000}>128 kbps</option>
              <option value={192000}>192 kbps</option>
              <option value={256000}>256 kbps</option>
            </select>
          </label>
          <label className={styles.toggle}>
            <span>Auto Answer</span>
            <input
              type="checkbox"
              checked={settings.auto_answer}
              onChange={(e) => save({ auto_answer: e.target.checked })}
            />
          </label>
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Latency</h3>
          <label className={styles.field}>
            <span>Capture (ms)</span>
            <input
              type="number"
              value={settings.capture_latency}
              min={2}
              max={200}
              onChange={(e) => save({ capture_latency: Number(e.target.value) })}
            />
          </label>
          <label className={styles.field}>
            <span>Playback (ms)</span>
            <input
              type="number"
              value={settings.playback_latency}
              min={2}
              max={200}
              onChange={(e) => save({ playback_latency: Number(e.target.value) })}
            />
          </label>
          <label className={styles.field}>
            <span>Period Size</span>
            <input
              type="number"
              value={settings.period_size}
              min={1}
              max={50}
              onChange={(e) => save({ period_size: Number(e.target.value) })}
            />
          </label>
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Hardware</h3>
          <label className={styles.toggle}>
            <span>Hardware Mixer</span>
            <input
              type="checkbox"
              checked={settings.hardware_mixer}
              onChange={(e) => save({ hardware_mixer: e.target.checked })}
            />
          </label>
          <label className={styles.toggle}>
            <span>48V Phantom Power</span>
            <input
              type="checkbox"
              checked={settings.phantom_power}
              onChange={(e) => save({ phantom_power: e.target.checked })}
            />
          </label>
        </div>
      </div>

      {saving && <div className={styles.saving}>Saving...</div>}
    </div>
  );
}
