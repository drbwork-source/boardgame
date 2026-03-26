/**
 * Optional sound effects for Play mode (dice, win, land on special).
 * Uses Web Audio API for minimal footprint; no asset files required.
 */

let audioContext: AudioContext | null = null;
let enabled = false;

const STORAGE_KEY = "boardgame-sound-enabled";

function getContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!audioContext) {
    try {
      audioContext = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    } catch {
      return null;
    }
  }
  return audioContext;
}

function beep(frequency: number, durationMs: number, type: OscillatorType = "sine"): void {
  const ctx = getContext();
  if (!ctx || !enabled) return;
  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = frequency;
    osc.type = type;
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + durationMs / 1000);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + durationMs / 1000);
  } catch {
    // ignore
  }
}

export function setSoundEnabled(value: boolean): void {
  enabled = value;
  try {
    localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
  } catch {
    // ignore
  }
}

export function isSoundEnabled(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) enabled = stored === "1";
  } catch {
    // ignore
  }
  return enabled;
}

export function playDiceRoll(): void {
  if (!enabled) return;
  beep(200, 40, "square");
  setTimeout(() => beep(400, 50, "square"), 80);
  setTimeout(() => beep(600, 60, "square"), 160);
}

export function playWin(): void {
  if (!enabled) return;
  [523, 659, 784, 1047].forEach((freq, i) => {
    setTimeout(() => beep(freq, 120, "sine"), i * 100);
  });
}

export function playLandOnSpecial(): void {
  if (!enabled) return;
  beep(440, 80, "sine");
  setTimeout(() => beep(554, 80, "sine"), 100);
}
