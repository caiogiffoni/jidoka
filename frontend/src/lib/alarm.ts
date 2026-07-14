export type AlarmSound = "digital" | "bell" | "none";

export const ALARM_SOUNDS: { value: AlarmSound; label: string }[] = [
  { value: "digital", label: "Digital" },
  { value: "bell", label: "Bell" },
  { value: "none", label: "None" },
];

// Synthesized with WebAudio so no sound assets ship with the app.
export function playAlarm(sound: AlarmSound, volume: number): void {
  if (sound === "none" || volume <= 0 || typeof AudioContext === "undefined") {
    return;
  }
  const ctx = new AudioContext();
  const gain = ctx.createGain();
  // Cap well below full scale; 100 should be loud, not clipping.
  const peak = (volume / 100) * 0.25;
  gain.connect(ctx.destination);

  const now = ctx.currentTime;
  let end: number;

  if (sound === "digital") {
    // Four short square beeps: beep-beep, beep-beep.
    const osc = ctx.createOscillator();
    osc.type = "square";
    osc.frequency.value = 880;
    osc.connect(gain);
    gain.gain.value = 0;
    for (const t of [0, 0.2, 0.55, 0.75]) {
      gain.gain.setValueAtTime(peak, now + t);
      gain.gain.setValueAtTime(0, now + t + 0.12);
    }
    end = now + 0.9;
    osc.start(now);
    osc.stop(end);
  } else {
    // A single strike with a long decay.
    const osc = ctx.createOscillator();
    osc.type = "sine";
    osc.frequency.value = 660;
    osc.connect(gain);
    gain.gain.setValueAtTime(peak, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.2);
    end = now + 1.2;
    osc.start(now);
    osc.stop(end);
  }

  window.setTimeout(() => void ctx.close(), (end - now) * 1000 + 100);
}
