import { Volume2, VolumeX, Mic, MicOff, Link, Unlink } from "lucide-react";
import { FaderSlider } from "./FaderSlider";
import styles from "./Fader.module.css";

interface Props {
  type: "playback" | "capture";
  leftLevel: number;
  rightLevel?: number;
  linked?: boolean;
  onMute: () => void;
  onLink?: (linked: boolean) => void;
  onSetLevel?: (channel: "l" | "r", level: number) => void;
}

export function Fader({ type, leftLevel, rightLevel, linked = true, onMute, onLink, onSetLevel }: Props) {
  const isCapture = type === "capture";
  const isMuted = leftLevel === 0 && (rightLevel ?? leftLevel) === 0;
  const Icon = isCapture ? (isMuted ? MicOff : Mic) : (isMuted ? VolumeX : Volume2);
  const label = isCapture ? "MIC" : "VOLUME";
  const stereo = !isCapture && !linked;

  const handleLevel = (channel: "l" | "r", level: number) => {
    if (onSetLevel) onSetLevel(channel, level);
  };

  return (
    <div className={styles.fader}>
      <span className={styles.label}>{label}</span>

      {/* Level readout */}
      {stereo ? (
        <div className={styles.levelDisplaySplit}>
          <span>L {leftLevel}</span>
          <span>R {rightLevel}</span>
        </div>
      ) : (
        <div className={styles.levelDisplay}>{leftLevel}</div>
      )}

      {/* Fader sliders */}
      <div className={styles.faders}>
        <FaderSlider
          level={leftLevel}
          muted={isMuted}
          onChange={(lvl) => handleLevel("l", lvl)}
        />
        {stereo && (
          <FaderSlider
            level={rightLevel ?? leftLevel}
            muted={isMuted}
            onChange={(lvl) => handleLevel("r", lvl)}
          />
        )}
      </div>

      {/* Mute + Link */}
      <div className={styles.actions}>
        <button
          className={`${styles.muteBtn} ${isMuted ? styles.muteBtnActive : ""}`}
          onClick={onMute}
        >
          <Icon size={24} />
        </button>
        {!isCapture && onLink && (
          <button
            className={`${styles.linkBtn} ${linked ? styles.linkBtnActive : ""}`}
            onClick={() => onLink(!linked)}
          >
            {linked ? <Link size={20} /> : <Unlink size={20} />}
          </button>
        )}
      </div>
    </div>
  );
}
