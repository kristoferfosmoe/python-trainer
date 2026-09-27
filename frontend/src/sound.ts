// Plays the hub's beeps during playback.

let audio: AudioContext | null = null;

export function beep(frequency: number, durationMs: number) {
  try {
    audio ??= new AudioContext();
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    const now = audio.currentTime;
    const seconds = Math.max(0.03, Math.min(durationMs, 2000) / 1000);
    osc.type = "square";
    osc.frequency.value = frequency;
    gain.gain.setValueAtTime(0.06, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + seconds);
    osc.connect(gain).connect(audio.destination);
    osc.start(now);
    osc.stop(now + seconds);
  } catch {
    // Sound is a bonus; ignore browsers that block it.
  }
}
