// Plays a trace back in robot time: a clock that runs from 0 to the end of
// the run at 0.5x-4x speed, playing the hub's beeps as it passes them.

import { useCallback, useEffect, useRef, useState } from "react";
import { eventsBetween } from "./playback";
import { beep } from "./sound";
import * as storage from "./storage";
import type { Trace } from "./types";

export function usePlayback(trace: Trace | null) {
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [sound, setSoundState] = useState(storage.soundOn);
  const clock = useRef({ time: 0, speed: 1, sound: true });
  clock.current.speed = speed;
  clock.current.sound = sound;

  const seek = useCallback((t: number) => {
    clock.current.time = t;
    setTime(t);
  }, []);

  useEffect(() => {
    if (!playing || !trace) return;
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const before = clock.current.time;
      const after = Math.min(trace.end.t, before + (now - last) * clock.current.speed);
      last = now;
      if (clock.current.sound) {
        for (const event of eventsBetween(trace, before, after)) {
          if (event.type === "beep") beep(event.frequency ?? 500, (event.duration ?? 100) / clock.current.speed);
        }
      }
      clock.current.time = after;
      setTime(after);
      if (after >= trace.end.t) {
        setPlaying(false);
        return;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, trace]);

  const end = trace?.end.t ?? 0;
  const finished = trace !== null && time >= end;

  return {
    time,
    end,
    finished,
    playing,
    speed,
    sound,
    seek,
    play: () => {
      if (finished) seek(0);
      setPlaying(true);
    },
    pause: () => setPlaying(false),
    /** Start from the beginning (after a new run). */
    restart: () => {
      seek(0);
      setPlaying(true);
    },
    skipToEnd: () => {
      setPlaying(false);
      seek(end);
    },
    setSpeed,
    setSound: (on: boolean) => {
      setSoundState(on);
      storage.saveSoundOn(on);
    },
  };
}
