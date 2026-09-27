// Per-device preferences. (Progress and code live in session.ts.)

function read<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return value === null ? fallback : (JSON.parse(value) as T);
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Private windows can block storage; the app still works without it.
  }
}

export const lastChallenge = () => read<string | null>("last-challenge", null);
export const saveLastChallenge = (challengeId: string) => write("last-challenge", challengeId);
export const soundOn = () => read<boolean>("sound", true);
export const saveSoundOn = (on: boolean) => write("sound", on);
