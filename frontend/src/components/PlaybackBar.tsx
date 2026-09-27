import { formatTime } from "../playback";

// Inline icons (emoji glyphs vary between computers).
const Icon = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="currentColor">
    <path d={d} />
  </svg>
);
const PLAY = "M8 5v14l11-7z";
const PAUSE = "M6 5h4v14H6zM14 5h4v14h-4z";
const REPLAY = "M12 5V1L7 6l5 5V7a6 6 0 1 1-6 6H4a8 8 0 1 0 8-8z";
const SOUND = "M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 8v8a4.5 4.5 0 0 0 2.5-4z";
const MUTED = "M3 9v6h4l5 5V4L7 9H3zm13.6 3 2.7-2.7-1.4-1.4-2.7 2.7-2.7-2.7-1.4 1.4 2.7 2.7-2.7 2.7 1.4 1.4 2.7-2.7 2.7 2.7 1.4-1.4z";

const SPEEDS = [0.5, 1, 2, 4];

interface Props {
  time: number;
  end: number;
  playing: boolean;
  speed: number;
  sound: boolean;
  onPlayPause: () => void;
  onSeek: (t: number) => void;
  onSpeed: (speed: number) => void;
  onSound: (on: boolean) => void;
}

export function PlaybackBar({ time, end, playing, speed, sound, onPlayPause, onSeek, onSpeed, onSound }: Props) {
  return (
    <div className="playback" aria-label="Playback controls">
      <button className="icon" onClick={onPlayPause} aria-label={playing ? "Pause" : "Play"} title={playing ? "Pause" : "Play"}>
        <Icon d={playing ? PAUSE : time >= end ? REPLAY : PLAY} />
      </button>
      <input
        type="range"
        min={0}
        max={Math.max(end, 1)}
        step={10}
        value={Math.min(time, end)}
        onChange={(e) => onSeek(Number(e.target.value))}
        aria-label="Robot time"
      />
      <span className="time">
        {formatTime(Math.min(time, end))} / {formatTime(end)}
      </span>
      <select value={speed} onChange={(e) => onSpeed(Number(e.target.value))} aria-label="Playback speed">
        {SPEEDS.map((s) => (
          <option key={s} value={s}>
            {s}×
          </option>
        ))}
      </select>
      <button className="icon" onClick={() => onSound(!sound)} aria-label={sound ? "Mute beeps" : "Unmute beeps"} title={sound ? "Mute" : "Unmute"}>
        <Icon d={sound ? SOUND : MUTED} />
      </button>
    </div>
  );
}
