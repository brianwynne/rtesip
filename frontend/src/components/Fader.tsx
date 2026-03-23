import { Volume2, VolumeX, Mic, MicOff, Link, Unlink } from "lucide-react";
import { Meter } from "./Meter";
import styles from "./Fader.module.css";

interface Props {
  type: "playback" | "capture";
  leftLevel: number;
  rightLevel: number;
  linked: boolean;
  onUp: (channel: "l" | "r") => void;
  onDown: (channel: "l" | "r") => void;
  onMute: () => void;
  onLink: (linked: boolean) => void;
}

export function Fader({ type, leftLevel, rightLevel, linked, onUp, onDown, onMute, onLink }: Props) {
  const isCapture = type === "capture";
  const isMuted = leftLevel === 0 && rightLevel === 0;
  const Icon = isCapture ? (isMuted ? MicOff : Mic) : (isMuted ? VolumeX : Volume2);
  const label = isCapture ? "INPUT" : "OUTPUT";

  return (
    <div className={styles.fader}>
      <div className={styles.header}>
        <button
          className={`${styles.muteBtn} ${isMuted ? styles.muteBtnActive : ""}`}
          onClick={onMute}
          title={isMuted ? "Unmute" : "Mute"}
        >
          <Icon size={16} />
        </button>
        <span className={styles.label}>{label}</span>
        <button
          className={`${styles.linkBtn} ${linked ? styles.linkBtnActive : ""}`}
          onClick={() => onLink(!linked)}
          title={linked ? "Unlink channels" : "Link channels"}
        >
          {linked ? <Link size={14} /> : <Unlink size={14} />}
        </button>
      </div>
      <div className={styles.meters}>
        <Meter label="L" level={leftLevel} muted={isMuted} />
        <Meter label="R" level={rightLevel} muted={isMuted} />
      </div>
      <div className={styles.controls}>
        <button className={styles.ctrlBtn} onClick={() => onDown("l")}>-</button>
        <button className={styles.ctrlBtn} onClick={() => onUp("l")}>+</button>
      </div>
    </div>
  );
}
