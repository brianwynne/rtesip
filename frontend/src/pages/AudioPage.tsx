import { useEffect, useState } from "react";
import styles from "./AudioPage.module.css";

const ALL_CODECS = [
  { id: "opus/48000/2", label: "Opus 48kHz" },
  { id: "L16/44100/1", label: "L16 44.1kHz (Linear PCM)" },
  { id: "G722/16000/1", label: "G.722 16kHz" },
  { id: "PCMA/8000/1", label: "G.711 A-law (PCMA)" },
  { id: "PCMU/8000/1", label: "G.711 μ-law (PCMU)" },
];

interface DetectedDevice {
  card: number;
  id: string;
  name: string;
  usb: boolean;
  capture_channels: number;
  playback_channels: number;
  has_agc: boolean;
  agc_on: boolean;
}

interface AudioSettings {
  channels: number;
  bitrate: number;
  input: string;
  output: string;
  input_routing: string;
  output_routing: string;
  input_left_device: string;
  input_left_channel: number;
  input_right_device: string;
  input_right_channel: number;
  output_left_device: string;
  output_left_channel: number;
  output_right_device: string;
  output_right_channel: number;
  ec_tail: number;
  opus_complexity: number;
  opus_cbr: boolean;
  opus_fec: boolean;
  opus_packet_loss: number;
  opus_frame_duration: number;
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

function deviceValue(dev: DetectedDevice): string {
  return dev.usb ? "USB" : `plughw:CARD=${dev.id},DEV=0`;
}

function getMaxChannels(
  devices: DetectedDevice[],
  deviceStr: string,
  direction: "capture" | "playback",
): number {
  const dev = devices.find(
    (d) => deviceValue(d) === deviceStr,
  );
  if (!dev) return 2;
  return direction === "capture" ? dev.capture_channels : dev.playback_channels;
}

function ChannelMapping({
  label,
  deviceStr,
  channel,
  devices,
  direction,
  onDeviceChange,
  onChannelChange,
}: {
  label: string;
  deviceStr: string;
  channel: number;
  devices: DetectedDevice[];
  direction: "capture" | "playback";
  onDeviceChange: (v: string) => void;
  onChannelChange: (v: number) => void;
}) {
  const maxCh = getMaxChannels(devices, deviceStr, direction);
  const filteredDevices =
    direction === "capture"
      ? devices.filter((d) => d.capture_channels > 0)
      : devices.filter((d) => d.playback_channels > 0);

  return (
    <div className={styles.channelRow}>
      <span className={styles.channelLabel}>{label}</span>
      <select
        className={styles.channelDevice}
        value={deviceStr}
        onChange={(e) => onDeviceChange(e.target.value)}
      >
        {filteredDevices.length > 0 ? (
          filteredDevices.map((d) => (
            <option key={d.card} value={deviceValue(d)}>
              {d.name}
            </option>
          ))
        ) : (
          <>
            <option value="USB">USB</option>
            <option value="plughw:CARD=sndrpihifiberry,DEV=0">HiFiBerry</option>
            <option value="plughw:CARD=AES67,DEV=0">AES67</option>
          </>
        )}
      </select>
      <select
        className={styles.channelSelect}
        value={channel}
        onChange={(e) => onChannelChange(Number(e.target.value))}
      >
        {maxCh > 1 && <option value={-1}>Mix</option>}
        {Array.from({ length: maxCh }, (_, i) => (
          <option key={i} value={i}>
            Ch {i + 1}
          </option>
        ))}
      </select>
    </div>
  );
}

export function AudioPage() {
  const [settings, setSettings] = useState<AudioSettings>({
    channels: 1,
    bitrate: 64000,
    input: "USB",
    output: "USB",
    input_routing: "lr",
    output_routing: "lr",
    input_left_device: "USB",
    input_left_channel: 0,
    input_right_device: "USB",
    input_right_channel: 1,
    output_left_device: "USB",
    output_left_channel: 0,
    output_right_device: "USB",
    output_right_channel: 1,
    ec_tail: 200,
    opus_complexity: 10,
    opus_cbr: false,
    opus_fec: false,
    opus_packet_loss: 10,
    opus_frame_duration: 20,
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
  const [detectedDevices, setDetectedDevices] = useState<DetectedDevice[]>([]);

  useEffect(() => {
    fetch("/api/audio/settings")
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(setSettings)
      .catch(() => {});
    fetch("/api/sip/settings")
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((data) => { if (data.codecs) setCodecs(data.codecs); })
      .catch(() => {});
    fetch("/api/audio/detected-devices")
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((data) => { if (data.devices) setDetectedDevices(data.devices); })
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

  const isStereo = settings.channels === 2;

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
          <label className={styles.field}>
            <span>Echo Cancel Tail</span>
            <div className={styles.fieldWithUnit}>
              <select
                value={settings.ec_tail}
                onChange={(e) => save({ ec_tail: Number(e.target.value) })}
              >
                <option value={0}>Off</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={400}>400</option>
              </select>
              <span className={styles.unit}>ms</span>
            </div>
          </label>
        </div>

        {/* Opus */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Opus</h3>
          <div className={styles.hint}>Changes apply after the current call ends.</div>
          <label className={styles.field}>
            <span>Bitrate</span>
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
            <span>Frame Duration</span>
            <div className={styles.fieldWithUnit}>
              <select
                value={settings.opus_frame_duration}
                onChange={(e) => save({ opus_frame_duration: Number(e.target.value) })}
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={40}>40</option>
                <option value={60}>60</option>
              </select>
              <span className={styles.unit}>ms</span>
            </div>
          </label>
          <label className={styles.field}>
            <span>Complexity</span>
            <select
              value={settings.opus_complexity}
              onChange={(e) => save({ opus_complexity: Number(e.target.value) })}
            >
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </label>
          <label className={styles.toggle}>
            <span>Constant Bitrate</span>
            <input
              type="checkbox"
              checked={settings.opus_cbr}
              onChange={(e) => save({ opus_cbr: e.target.checked })}
            />
          </label>
          <label className={styles.toggle}>
            <span>FEC</span>
            <input
              type="checkbox"
              checked={settings.opus_fec}
              onChange={(e) => save({ opus_fec: e.target.checked })}
            />
          </label>
          {settings.opus_fec && (
            <label className={styles.field}>
              <span>Expected Loss</span>
              <div className={styles.fieldWithUnit}>
                <input
                  type="number"
                  value={settings.opus_packet_loss}
                  min={1}
                  max={100}
                  onChange={(e) => save({ opus_packet_loss: Number(e.target.value) })}
                />
                <span className={styles.unit}>%</span>
              </div>
            </label>
          )}
        </div>

        {/* Input */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Input</h3>
          <div className={styles.hint}>Changes apply after the current call ends.</div>
          {isStereo ? (
            <>
              <ChannelMapping
                label="Left"
                deviceStr={settings.input_left_device}
                channel={settings.input_left_channel}
                devices={detectedDevices}
                direction="capture"
                onDeviceChange={(v) => save({ input_left_device: v })}
                onChannelChange={(v) => save({ input_left_channel: v })}
              />
              <ChannelMapping
                label="Right"
                deviceStr={settings.input_right_device}
                channel={settings.input_right_channel}
                devices={detectedDevices}
                direction="capture"
                onDeviceChange={(v) => save({ input_right_device: v })}
                onChannelChange={(v) => save({ input_right_channel: v })}
              />
            </>
          ) : (
            <ChannelMapping
              label="Channel"
              deviceStr={settings.input_left_device}
              channel={settings.input_left_channel}
              devices={detectedDevices}
              direction="capture"
              onDeviceChange={(v) => save({ input_left_device: v })}
              onChannelChange={(v) => save({ input_left_channel: v })}
            />
          )}
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
          {(() => {
            const dev = detectedDevices.find(
              (d) => deviceValue(d) === settings.input_left_device,
            );
            return dev?.has_agc ? (
              <label className={styles.toggle}>
                <span>Auto Gain Control</span>
                <input
                  type="checkbox"
                  checked={dev.agc_on}
                  onChange={(e) => {
                    fetch("/api/audio/agc", {
                      method: "PUT",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ card: dev.card, enabled: e.target.checked }),
                    }).then(() => {
                      setDetectedDevices((prev) =>
                        prev.map((d) => d.card === dev.card ? { ...d, agc_on: e.target.checked } : d)
                      );
                    }).catch(() => {});
                  }}
                />
              </label>
            ) : null;
          })()}
        </div>

        {/* Output */}
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Output</h3>
          <div className={styles.hint}>Changes apply after the current call ends.</div>
          {isStereo ? (
            <>
              <ChannelMapping
                label="Left"
                deviceStr={settings.output_left_device}
                channel={settings.output_left_channel}
                devices={detectedDevices}
                direction="playback"
                onDeviceChange={(v) => save({ output_left_device: v })}
                onChannelChange={(v) => save({ output_left_channel: v })}
              />
              <ChannelMapping
                label="Right"
                deviceStr={settings.output_right_device}
                channel={settings.output_right_channel}
                devices={detectedDevices}
                direction="playback"
                onDeviceChange={(v) => save({ output_right_device: v })}
                onChannelChange={(v) => save({ output_right_channel: v })}
              />
            </>
          ) : (
            <ChannelMapping
              label="Channel"
              deviceStr={settings.output_left_device}
              channel={settings.output_left_channel}
              devices={detectedDevices}
              direction="playback"
              onDeviceChange={(v) => save({ output_left_device: v })}
              onChannelChange={(v) => save({ output_left_channel: v })}
            />
          )}
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
                <span className={styles.codecId}>
                  {c.id.startsWith("L16/") ? `L16/44100/${isStereo ? 2 : 1}` : c.id}
                </span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {saving && <div className={styles.saving}>Saving...</div>}
    </div>
  );
}
