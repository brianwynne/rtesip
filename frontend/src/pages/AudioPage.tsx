import { useEffect, useState } from "react";
import styles from "./AudioPage.module.css";

const ALL_CODECS = [
  { id: "opus/48000/2", label: "Opus 48kHz Stereo" },
  { id: "L16/44100/1", label: "L16 44.1kHz (Linear PCM)" },
  { id: "G722/16000/1", label: "G.722 16kHz" },
  { id: "PCMA/8000/1", label: "G.711 A-law (PCMA)" },
  { id: "PCMU/8000/1", label: "G.711 μ-law (PCMU)" },
];

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
  capture_volume: number;
  playback_volume: number;
  auto_answer: boolean;
  mic_monitor: boolean;
  hardware_mixer: boolean;
  phantom_power: boolean;
}

export function AudioPage() {
  const [settings, setSettings] = useState<AudioSettings>({
    channels: 1,
    bitrate: 64000,
    input: "USB",
    output: "USB",
    input_routing: "lr",
    output_routing: "lr",
    capture_latency: 10,
    playback_latency: 10,
    period_size: 5,
    capture_volume: 100,
    playback_volume: 100,
    auto_answer: false,
    mic_monitor: false,
    hardware_mixer: false,
    phantom_power: false,
  });
  const [codecs, setCodecs] = useState<string[]>(["opus/48000/2", "G722/16000/1"]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/audio/settings")
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setSettings)
      .catch(() => {});
    fetch("/api/sip/settings")
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((data) => { if (data.codecs) setCodecs(data.codecs); })
      .catch(() => {});
  }, []);

  const save = async (updates: Partial<AudioSettings>) => {
    setSaving(true);
    try {
      const res = await fetch("/api/audio/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (res.ok) setSettings(await res.json());
    } catch {
      // network error
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.page}>
      <h2 className={styles.heading}>Audio Configuration</h2>

      <div className={styles.grid}>
        {/* General */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>General</h3>
          <label className={styles.field}>
            <span>Auto Answer</span>
            <select
              value={settings.auto_answer ? "on" : "off"}
              onChange={(e) => save({ auto_answer: e.target.value === "on" })}
            >
              <option value="off">Off</option>
              <option value="on">On</option>
            </select>
          </label>
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
            <span>Opus Bandwidth</span>
            <div className={styles.fieldWithUnit}>
              <select
                value={settings.bitrate}
                onChange={(e) => save({ bitrate: Number(e.target.value) })}
              >
                <option value={32000}>32</option>
                <option value={48000}>48</option>
                <option value={64000}>64</option>
                <option value={72000}>72</option>
                <option value={96000}>96</option>
                <option value={128000}>128</option>
                <option value={192000}>192</option>
                <option value={256000}>256</option>
              </select>
              <span className={styles.unit}>kbps</span>
            </div>
          </label>
          <label className={styles.field}>
            <span>Buffer Period Size</span>
            <div className={styles.fieldWithUnit}>
              <input
                type="number"
                value={settings.period_size}
                min={1}
                max={50}
                onChange={(e) => save({ period_size: Number(e.target.value) })}
              />
              <span className={styles.unit}>ms</span>
            </div>
          </label>
        </div>

        {/* Input */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Input</h3>
          <label className={styles.field}>
            <span>Input Device</span>
            <select
              value={settings.input}
              onChange={(e) => save({ input: e.target.value })}
            >
              <option value="USB">First USB Device</option>
              <option value="plughw:CARD=sndrpihifiberry,DEV=0">HiFiBerry</option>
              <option value="plughw:CARD=AES67,DEV=0">AES67</option>
            </select>
          </label>
          <label className={styles.field}>
            <span>Routing</span>
            <select
              value={settings.input_routing}
              onChange={(e) => save({ input_routing: e.target.value })}
            >
              {settings.channels === 2 ? (
                <>
                  <option value="lr">LR (Stereo)</option>
                  <option value="ll">LL (Left only)</option>
                  <option value="rr">RR (Right only)</option>
                  <option value="rl">RL (Swap)</option>
                  <option value="mono">Mono (L+R mix)</option>
                </>
              ) : (
                <>
                  <option value="ll">Left</option>
                  <option value="rr">Right</option>
                  <option value="mono">Mix (L+R)</option>
                </>
              )}
            </select>
          </label>
          <label className={styles.field}>
            <span>Capture Latency</span>
            <div className={styles.fieldWithUnit}>
              <input
                type="number"
                value={settings.capture_latency}
                min={2}
                max={200}
                onChange={(e) => save({ capture_latency: Number(e.target.value) })}
              />
              <span className={styles.unit}>ms</span>
            </div>
          </label>
          <label className={styles.field}>
            <span>Input Gain</span>
            <div className={styles.fieldWithUnit}>
              <input
                type="number"
                value={settings.capture_volume}
                min={0}
                max={100}
                onChange={(e) => save({ capture_volume: Number(e.target.value) })}
              />
              <span className={styles.unit}>%</span>
            </div>
          </label>
        </div>

        {/* Output */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Output</h3>
          <label className={styles.field}>
            <span>Output Device</span>
            <select
              value={settings.output}
              onChange={(e) => save({ output: e.target.value })}
            >
              <option value="USB">First USB Device</option>
              <option value="plughw:CARD=sndrpihifiberry,DEV=0">HiFiBerry</option>
              <option value="plughw:CARD=AES67,DEV=0">AES67</option>
            </select>
          </label>
          <label className={styles.field}>
            <span>Routing</span>
            <select
              value={settings.output_routing}
              onChange={(e) => save({ output_routing: e.target.value })}
            >
              {settings.channels === 2 ? (
                <>
                  <option value="lr">LR (Stereo)</option>
                  <option value="ll">LL (Left only)</option>
                  <option value="rr">RR (Right only)</option>
                  <option value="rl">RL (Swap)</option>
                  <option value="mono">Mono (L+R mix)</option>
                </>
              ) : (
                <>
                  <option value="ll">Left</option>
                  <option value="rr">Right</option>
                  <option value="mono">Mix (L+R)</option>
                </>
              )}
            </select>
          </label>
          <label className={styles.field}>
            <span>Output Latency</span>
            <div className={styles.fieldWithUnit}>
              <input
                type="number"
                value={settings.playback_latency}
                min={2}
                max={200}
                onChange={(e) => save({ playback_latency: Number(e.target.value) })}
              />
              <span className={styles.unit}>ms</span>
            </div>
          </label>
          <label className={styles.field}>
            <span>System Volume</span>
            <div className={styles.fieldWithUnit}>
              <input
                type="number"
                value={settings.playback_volume}
                min={0}
                max={100}
                onChange={(e) => save({ playback_volume: Number(e.target.value) })}
              />
              <span className={styles.unit}>%</span>
            </div>
          </label>
        </div>

        {/* Hardware */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Hardware</h3>
          <label className={styles.toggle}>
            <span>Hardware Mixing</span>
            <input
              type="checkbox"
              checked={settings.hardware_mixer}
              onChange={(e) => save({ hardware_mixer: e.target.checked })}
            />
          </label>
          <label className={styles.toggle}>
            <span>Mic Monitoring</span>
            <input
              type="checkbox"
              checked={settings.mic_monitor}
              onChange={(e) => save({ mic_monitor: e.target.checked })}
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
          {settings.mic_monitor && (
            <div className={styles.hint}>Optimise latency before using mic monitoring.</div>
          )}
        </div>

        {/* Codecs */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Codecs</h3>
          <div className={styles.codecList}>
            {ALL_CODECS.map((c) => (
              <label key={c.id} className={styles.codecItem}>
                <input
                  type="checkbox"
                  checked={codecs.includes(c.id)}
                  onChange={() => {
                    const selected = codecs.includes(c.id)
                      ? codecs.filter((x) => x !== c.id)
                      : [...codecs, c.id];
                    // Maintain ALL_CODECS display order
                    const updated = ALL_CODECS.map((ac) => ac.id).filter((id) => selected.includes(id));
                    setCodecs(updated);
                    fetch("/api/sip/settings", {
                      method: "PUT",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ codecs: updated }),
                    }).catch(() => {});
                  }}
                />
                <span className={styles.codecName}>{c.label}</span>
                <span className={styles.codecId}>{c.id}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {saving && <div className={styles.saving}>Saving...</div>}
    </div>
  );
}
