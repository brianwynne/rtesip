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
  onMuteVol: () => void;
  onMuteGain: () => void;
  onLinkVol: (linked: boolean) => void;
  onSetVolLevel?: (ch: "l" | "r", level: number) => void;
  onSetGainLevel?: (ch: "l" | "r", level: number) => void;
  sipReady: boolean;
}

export function CallPage(props: Props) {
  return (
    <div className={styles.page}>
      <Fader
        type="capture"
        leftLevel={props.volume.cl}
        onMute={props.onMuteGain}
        onSetLevel={props.onSetGainLevel}
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
        onMute={props.onMuteVol}
        onLink={props.onLinkVol}
        onSetLevel={props.onSetVolLevel}
      />
    </div>
  );
}
