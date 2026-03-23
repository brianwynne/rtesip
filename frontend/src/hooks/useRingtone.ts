import { useEffect, useRef } from "react";

/**
 * Generates a professional double-pulse ring tone using Web Audio API.
 * No external audio files needed.
 */
export function useRingtone(ringing: boolean) {
  const ctxRef = useRef<AudioContext | null>(null);
  const intervalRef = useRef<number>();

  useEffect(() => {
    if (!ringing) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
      return;
    }

    // Create audio context on first ring (requires user gesture in some browsers)
    if (!ctxRef.current) {
      ctxRef.current = new AudioContext();
    }
    const ctx = ctxRef.current;
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }

    const playBurst = () => {
      // Double pulse: two short tones with a gap, like a UK/IE phone ring
      const now = ctx.currentTime;

      for (let i = 0; i < 2; i++) {
        const offset = i * 0.25;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = "sine";
        osc.frequency.value = 440;

        gain.gain.setValueAtTime(0, now + offset);
        gain.gain.linearRampToValueAtTime(0.15, now + offset + 0.02);
        gain.gain.setValueAtTime(0.15, now + offset + 0.15);
        gain.gain.linearRampToValueAtTime(0, now + offset + 0.2);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now + offset);
        osc.stop(now + offset + 0.22);
      }
    };

    // Play immediately, then every 2 seconds
    playBurst();
    intervalRef.current = window.setInterval(playBurst, 2000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
      if (ctxRef.current) {
        ctxRef.current.close().catch(() => {});
        ctxRef.current = null;
      }
    };
  }, [ringing]);
}
