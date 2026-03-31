import { useRef, useEffect, useState, useCallback } from "react";
import { X } from "lucide-react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import type { CallQuality } from "../types";
import styles from "./QualityGraph.module.css";

interface Props {
  history: { t: number; q: CallQuality }[];
  onClose: () => void;
}

type MetricKey = "jitter" | "loss" | "bitrate" | "rtt" | "packets";

interface MetricDef {
  key: MetricKey;
  label: string;
  unit: string;
  series: { label: string; colorVar: string; extract: (q: CallQuality) => number | null }[];
}

const METRICS: MetricDef[] = [
  {
    key: "jitter", label: "Jitter", unit: "ms",
    series: [
      { label: "RX", colorVar: "--green", extract: (q) => q.rx_jitter_last ?? null },
      { label: "TX", colorVar: "--amber", extract: (q) => q.tx_jitter_last ?? null },
    ],
  },
  {
    key: "loss", label: "Packet Loss", unit: "%",
    series: [
      { label: "RX", colorVar: "--red", extract: (q) => q.rx_loss_pct ?? null },
      { label: "TX", colorVar: "--amber", extract: (q) => q.tx_loss_pct ?? null },
    ],
  },
  {
    key: "bitrate", label: "Bitrate", unit: "Kbps",
    series: [
      { label: "RX", colorVar: "--green", extract: (q) => q.rx_bitrate ?? null },
      { label: "TX", colorVar: "--amber", extract: (q) => q.tx_bitrate ?? null },
    ],
  },
  {
    key: "rtt", label: "Round-Trip Time", unit: "ms",
    series: [
      { label: "RTT", colorVar: "--green", extract: (q) => q.rtt_last ?? null },
    ],
  },
  {
    key: "packets", label: "Packets", unit: "pkt",
    series: [
      { label: "RX", colorVar: "--green", extract: (q) => q.rx_packets ?? null },
      { label: "TX", colorVar: "--amber", extract: (q) => q.tx_packets ?? null },
    ],
  },
];

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// Scale font for high-DPI canvas rendering
const DPR = window.devicePixelRatio || 1;
const AXIS_FONT = `${Math.round(14 * DPR)}px monospace`;
const LABEL_FONT = `bold ${Math.round(14 * DPR)}px monospace`;
const AXIS_SIZE = Math.round(55 * DPR);

function makeChart(
  el: HTMLElement,
  seriesDefs: { label: string; color: string }[],
  data: uPlot.AlignedData,
  yLabel: string,
  height: number,
): uPlot {
  const textColor = cssVar("--text-muted") || "#999";
  const gridColor = cssVar("--border") || "#333";

  const opts: uPlot.Options = {
    width: el.clientWidth,
    height,
    scales: { x: { time: false }, y: { auto: true } },
    axes: [
      {
        stroke: textColor,
        grid: { stroke: gridColor, width: 1 },
        ticks: { show: false },
        values: (_u, vals) => vals.map((v) => {
          const s = Math.max(0, Math.round(v));
          const m = Math.floor(s / 60);
          const sec = s % 60;
          return `${m}:${String(sec).padStart(2, "0")}`;
        }),
        font: AXIS_FONT,
      },
      {
        stroke: textColor,
        grid: { stroke: gridColor, width: 1 },
        ticks: { show: false },
        font: AXIS_FONT,
        label: yLabel,
        labelFont: LABEL_FONT,
        size: AXIS_SIZE,
      },
    ],
    series: [
      {},
      ...seriesDefs.map((s) => ({
        label: s.label,
        stroke: s.color,
        width: 2,
        points: { show: false },
      })),
    ],
    legend: { show: false },
    cursor: { show: true, drag: { x: false, y: false } },
    padding: [10, 16, 0, 0],
  };

  return new uPlot(opts, data, el);
}

export function QualityGraph({ history, onClose }: Props) {
  const [enabled, setEnabled] = useState<Set<MetricKey>>(new Set(["jitter", "loss", "rtt"]));
  const chartRefs = useRef<Map<MetricKey, HTMLDivElement>>(new Map());
  const chartsRef = useRef<Map<MetricKey, uPlot>>(new Map());

  const setChartRef = useCallback((key: MetricKey) => (el: HTMLDivElement | null) => {
    if (el) chartRefs.current.set(key, el);
    else chartRefs.current.delete(key);
  }, []);

  const toggle = useCallback((key: MetricKey) => {
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // Calculate chart height based on number of enabled metrics
  const activeMetrics = METRICS.filter((m) => enabled.has(m.key));
  // Reserve ~48px for header, ~48px for toggles, rest split among charts
  const chartHeight = activeMetrics.length > 0
    ? Math.max(120, Math.floor((window.innerHeight - 140) / activeMetrics.length))
    : 200;

  // Build/rebuild charts when enabled metrics or history changes
  useEffect(() => {
    // Destroy charts for disabled metrics
    for (const [key, chart] of chartsRef.current) {
      if (!enabled.has(key)) {
        chart.destroy();
        chartsRef.current.delete(key);
      }
    }

    if (history.length < 2) return;

    const t0 = history[0].t;
    const times = history.map((h) => h.t - t0);

    for (const metric of METRICS) {
      if (!enabled.has(metric.key)) continue;
      const el = chartRefs.current.get(metric.key);
      if (!el) continue;

      const seriesData = metric.series.map((s) =>
        history.map((h) => s.extract(h.q))
      );
      const data = [times, ...seriesData] as uPlot.AlignedData;

      const existing = chartsRef.current.get(metric.key);
      if (existing) {
        // Update data and resize
        existing.setSize({ width: el.clientWidth, height: chartHeight });
        existing.setData(data);
      } else {
        // Create new chart
        const seriesDefs = metric.series.map((s) => ({
          label: s.label,
          color: cssVar(s.colorVar) || "#999",
        }));
        const chart = makeChart(el, seriesDefs, data, metric.unit, chartHeight);
        chartsRef.current.set(metric.key, chart);
      }
    }
  }, [history.length, enabled, chartHeight]);

  // Resize on window resize
  useEffect(() => {
    const onResize = () => {
      for (const [key, chart] of chartsRef.current) {
        const el = chartRefs.current.get(key);
        if (el) chart.setSize({ width: el.clientWidth, height: chartHeight });
      }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [chartHeight]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      chartsRef.current.forEach((c) => c.destroy());
      chartsRef.current.clear();
    };
  }, []);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>Call Quality</span>
          <div className={styles.toggles}>
            {METRICS.map((m) => (
              <button
                key={m.key}
                className={`${styles.toggleBtn} ${enabled.has(m.key) ? styles.toggleActive : ""}`}
                onClick={() => toggle(m.key)}
              >
                {m.label}
              </button>
            ))}
          </div>
          <button className={styles.closeBtn} onClick={onClose}><X size={18} /></button>
        </div>

        <div className={styles.chartsArea}>
          {history.length < 2 ? (
            <div className={styles.waiting}>Accumulating data...</div>
          ) : (
            activeMetrics.map((m) => (
              <div key={m.key} className={styles.chartSection}>
                <div className={styles.chartHeader}>
                  <span className={styles.chartLabel}>{m.label} ({m.unit})</span>
                  <div className={styles.legend}>
                    {m.series.map((s) => (
                      <span key={s.label} className={styles.legendItem}>
                        <span className={styles.legendSwatch} style={{ background: cssVar(s.colorVar) }} />
                        {s.label}
                      </span>
                    ))}
                  </div>
                </div>
                <div ref={setChartRef(m.key)} className={styles.chart} />
              </div>
            ))
          )}
          {activeMetrics.length === 0 && history.length >= 2 && (
            <div className={styles.waiting}>Select a metric above</div>
          )}
        </div>
      </div>
    </div>
  );
}
