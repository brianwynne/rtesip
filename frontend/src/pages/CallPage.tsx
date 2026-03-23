import { CallPanel } from "../components/CallPanel";
import { Fader } from "../components/Fader";
import type { CallState, VolumeState, Contact } from "../types";
import styles from "./CallPage.module.css";

interface Props {
  callState: CallState;
  volume: VolumeState;
  contacts: Contact[];
  onCall: (address: string) => void;
  onHangup: () => void;
  onAnswer: () => void;
  onReject: () => void;
  onVolUp: (ch: "l" | "r") => void;
  onVolDown: (ch: "l" | "r") => void;
  onGainUp: (ch: "l" | "r") => void;
  onGainDown: (ch: "l" | "r") => void;
  onMuteVol: () => void;
  onMuteGain: () => void;
  onLinkVol: (linked: boolean) => void;
  onLinkGain: (linked: boolean) => void;
  onSetVolLevel?: (ch: "l" | "r", level: number) => void;
  onSetGainLevel?: (ch: "l" | "r", level: number) => void;
  sipReady: boolean;
  meterLevels: { cap_l: number; cap_r: number; play_l: number; play_r: number };
}

export function CallPage(props: Props) {
  return (
    <div className={styles.page}>
      <Fader
        type="capture"
        leftLevel={props.volume.cl}
        rightLevel={props.volume.cr}
        linked={props.volume.clink}
        onUp={props.onGainUp}
        onDown={props.onGainDown}
        onMute={props.onMuteGain}
        onLink={props.onLinkGain}
        onSetLevel={props.onSetGainLevel}
        meterLeft={props.meterLevels.cap_l}
        meterRight={props.meterLevels.cap_r}
      />
      <div className={styles.callSection}>
        <CallPanel
          callState={props.callState}
          sipReady={props.sipReady}
          onCall={props.onCall}
          onHangup={props.onHangup}
          onAnswer={props.onAnswer}
          onReject={props.onReject}
          contacts={props.contacts}
        />
      </div>
      <Fader
        type="playback"
        leftLevel={props.volume.pl}
        rightLevel={props.volume.pr}
        linked={props.volume.plink}
        onUp={props.onVolUp}
        onDown={props.onVolDown}
        onMute={props.onMuteVol}
        onLink={props.onLinkVol}
        onSetLevel={props.onSetVolLevel}
        meterLeft={props.meterLevels.play_l}
        meterRight={props.meterLevels.play_r}
      />
    </div>
  );
}
