import { Volume2, VolumeX, Mic, MicOff, Link, Unlink } from "lucide-react";
import { FaderSlider } from "./FaderSlider";
import { Meter } from "./Meter";
import styles from "./Fader.module.css";

interface Props {
  type: "playback" | "capture";
  leftLevel: number;
  rightLevel: number;
  linked: boolean;
  meterLeft?: number;
  meterRight?: number;
  onUp: (channel: "l" | "r") => void;
  onDown: (channel: "l" | "r") => void;
  onMute: () => void;
  onLink: (linked: boolean) => void;
  onSetLevel?: (channel: "l" | "r", level: number) => void;
}

export function Fader({ type, leftLevel, rightLevel, linked, meterLeft = 0, meterRight = 0, onMute, onLink, onUp, onDown, onSetLevel }: Props) {
  const isCapture = type === "capture";
  const isMuted = leftLevel === 0 && rightLevel === 0;
  const Icon = isCapture ? (isMuted ? MicOff : Mic) : (isMuted ? VolumeX : Volume2);
  const label = isCapture ? "INPUTS" : "OUTPUTS";
  const chLabelL = isCapture && !linked ? "Mic 1" : "L";
  const chLabelR = isCapture && !linked ? "Mic 2" : "R";

  const handleLevel = (channel: "l" | "r", level: number) => {
    if (onSetLevel) {
      onSetLevel(channel, level);
    } else {
      const current = channel === "l" ? leftLevel : rightLevel;
      const diff = level - current;
      const steps = Math.abs(Math.round(diff / 10));
      const fn = diff > 0 ? onUp : onDown;
      for (let i = 0; i < steps; i++) fn(channel);
    }
  };

  return (
    <div className={styles.fader}>
      <span className={styles.label}>{label}</span>

      {/* Meters */}
      <div className={styles.meters}>
        <Meter label={chLabelL} level={meterLeft} muted={isMuted} vertical scalePosition="left" maxLevel={100} />
        <Meter label={chLabelR} level={meterRight} muted={isMuted} vertical scalePosition="right" maxLevel={100} />
      </div>

      {/* Per-channel level readout (unlinked) */}
      {!linked && (
        <div className={styles.levelDisplaySplit}>
          <span>{leftLevel}%</span>
          <span>{rightLevel}%</span>
        </div>
      )}

      {/* Fader sliders */}
      <div className={styles.faders}>
        <FaderSlider
          level={leftLevel}
          muted={isMuted}
          onChange={(lvl) => handleLevel("l", lvl)}
        />
        {!linked ? (
          <FaderSlider
            level={rightLevel}
            muted={isMuted}
            onChange={(lvl) => handleLevel("r", lvl)}
          />
        ) : (
          <FaderSlider
            level={rightLevel}
            muted={isMuted}
            onChange={(lvl) => handleLevel("l", lvl)}
          />
        )}
      </div>

      {/* Level readout (linked) */}
      {linked && (
        <div className={styles.levelDisplay}>
          {leftLevel}%
        </div>
      )}

      {/* Mute + Link */}
      <div className={styles.actions}>
        <button
          className={`${styles.muteBtn} ${isMuted ? styles.muteBtnActive : ""}`}
          onClick={onMute}
        >
          <Icon size={24} />
        </button>
        <button
          className={`${styles.linkBtn} ${linked ? styles.linkBtnActive : ""}`}
          onClick={() => onLink(!linked)}
        >
          {linked ? <Link size={20} /> : <Unlink size={20} />}
        </button>
      </div>
    </div>
  );
}
