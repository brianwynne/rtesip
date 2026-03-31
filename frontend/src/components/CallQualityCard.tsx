import { useState } from "react";
import { X, BarChart3 } from "lucide-react";
import type { CallState, CallQuality } from "../types";
import { QualityGraph } from "./QualityGraph";
import styles from "./CallQualityCard.module.css";

interface Props {
  callState: CallState;
  history: { t: number; q: CallQuality }[];
  onClose: () => void;
}

function fmt(v: number | undefined, unit: string, decimals = 1): string {
  if (v == null) return "--";
  return `${v.toFixed(decimals)} ${unit}`;
}

function lossClass(pct: number | undefined): string {
  if (pct == null) return "";
  if (pct === 0) return styles.good;
  if (pct < 2) return styles.warn;
  return styles.bad;
}

function jitterClass(ms: number | undefined): string {
  if (ms == null) return "";
  if (ms < 20) return styles.good;
  if (ms < 50) return styles.warn;
  return styles.bad;
}

function rttClass(ms: number | undefined): string {
  if (ms == null) return "";
  if (ms < 100) return styles.good;
  if (ms < 300) return styles.warn;
  return styles.bad;
}

export function CallQualityCard({ callState, history, onClose }: Props) {
  const q = callState.quality;
  const [showGraphs, setShowGraphs] = useState(false);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.card} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>Call Quality</span>
          <button className={styles.close} onClick={onClose}><X size={14} /></button>
        </div>

        {/* Codec & Security */}
        <div className={styles.section}>
          <div className={styles.sectionLabel}>Media</div>
          <div className={styles.row}>
            <span className={styles.label}>Codec</span>
            <span className={styles.value}>{callState.codec || "--"}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Encryption</span>
            <span className={`${styles.value} ${callState.srtpActive ? styles.good : styles.bad}`}>
              {callState.srtpActive ? (callState.srtpSuite || "SRTP") : "None"}
            </span>
          </div>
        </div>

        {!q ? (
          <div className={styles.waiting}>Collecting metrics...</div>
        ) : (
          <>
            {/* Bitrate */}
            {(q.rx_bitrate != null || q.tx_bitrate != null) && (
              <div className={styles.section}>
                <div className={styles.sectionLabel}>Bitrate{q.target_bitrate ? ` (target ${q.target_bitrate} Kbps)` : ""}</div>
                <div className={styles.row}>
                  <span className={styles.label}>RX</span>
                  <span className={styles.value}>{q.rx_bitrate != null ? `${q.rx_bitrate} Kbps` : "--"}</span>
                </div>
                <div className={styles.row}>
                  <span className={styles.label}>TX</span>
                  <span className={styles.value}>{q.tx_bitrate != null ? `${q.tx_bitrate} Kbps` : "--"}</span>
                </div>
              </div>
            )}

            {/* Jitter */}
            <div className={styles.section}>
              <div className={styles.sectionLabel}>Jitter</div>
              <div className={styles.row}>
                <span className={styles.label}>RX (current)</span>
                <span className={`${styles.value} ${jitterClass(q.rx_jitter_last)}`}>
                  {fmt(q.rx_jitter_last, "ms")}
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.label}>RX (avg / max)</span>
                <span className={styles.value}>
                  {fmt(q.rx_jitter_avg, "ms")} / {fmt(q.rx_jitter_max, "ms")}
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.label}>TX (current)</span>
                <span className={`${styles.value} ${jitterClass(q.tx_jitter_last)}`}>
                  {fmt(q.tx_jitter_last, "ms")}
                </span>
              </div>
            </div>

            {/* Packet Loss */}
            <div className={styles.section}>
              <div className={styles.sectionLabel}>Packet Loss</div>
              <div className={styles.row}>
                <span className={styles.label}>RX</span>
                <span className={`${styles.value} ${lossClass(q.rx_loss_pct)}`}>
                  {q.rx_lost != null ? `${q.rx_lost} pkt` : "--"} ({fmt(q.rx_loss_pct, "%")})
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.label}>TX</span>
                <span className={`${styles.value} ${lossClass(q.tx_loss_pct)}`}>
                  {q.tx_lost != null ? `${q.tx_lost} pkt` : "--"} ({fmt(q.tx_loss_pct, "%")})
                </span>
              </div>
            </div>

            {/* RTT */}
            <div className={styles.section}>
              <div className={styles.sectionLabel}>Round-Trip Time</div>
              <div className={styles.row}>
                <span className={styles.label}>Current</span>
                <span className={`${styles.value} ${rttClass(q.rtt_last)}`}>
                  {fmt(q.rtt_last, "ms")}
                </span>
              </div>
              <div className={styles.row}>
                <span className={styles.label}>Average</span>
                <span className={styles.value}>{fmt(q.rtt_avg, "ms")}</span>
              </div>
            </div>

            {/* Packets */}
            <div className={styles.section}>
              <div className={styles.sectionLabel}>Packets</div>
              <div className={styles.row}>
                <span className={styles.label}>RX / TX</span>
                <span className={styles.value}>
                  {q.rx_packets?.toLocaleString() ?? "--"} / {q.tx_packets?.toLocaleString() ?? "--"}
                </span>
              </div>
            </div>

            {/* Graphs pop-out */}
            <button className={styles.graphToggle} onClick={() => setShowGraphs(true)}>
              <BarChart3 size={14} />
              <span>Show Graphs</span>
            </button>

            {showGraphs && <QualityGraph history={history} onClose={() => setShowGraphs(false)} />}
          </>
        )}
      </div>
    </div>
  );
}
