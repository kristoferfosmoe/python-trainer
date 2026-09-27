"""Simulated ``pybricks.hubs``: the SPIKE Prime hub."""

import re

from trainer_sim.context import current
from trainer_sim.errors import NotInSimulator

from ._args import number
from .parameters import Color, Side


class _IMU:
    def __init__(self, sim):
        self._sim = sim

    def heading(self):
        return round(self._sim.gyro_heading() - self._sim.imu_offset, 1)

    def reset_heading(self, angle):
        self._sim.imu_offset = self._sim.gyro_heading() - number(angle, "angle", "reset_heading")

    def angular_velocity(self, axis=None):
        rate = round(self._sim.turn_rate, 1)
        return rate if axis is not None else (0.0, 0.0, rate)

    def acceleration(self, axis=None):
        return 0.0 if axis is not None else (0.0, 0.0, 9810.0)

    def tilt(self):
        return (0, 0)

    def up(self):
        return Side.TOP

    def ready(self):
        return True

    def stationary(self):
        return abs(self._sim.turn_rate) < 1 and abs(self._sim.speed) < 1

    def settings(self, *args, **kwargs):
        return None

    def rotation(self, *args, **kwargs):
        raise NotInSimulator("hub.imu.rotation()")


class _Light:
    def __init__(self, sim):
        self._sim = sim

    def on(self, color):
        name = color.name if isinstance(color, Color) else None
        self._sim.event("light", color=(name or "WHITE").lower() if color != Color.NONE else "off")

    def off(self):
        self._sim.event("light", color="off")

    def blink(self, color, durations):
        self.on(color)

    def animate(self, colors, interval):
        if colors:
            self.on(colors[0])


class _Display:
    def __init__(self, sim):
        self._sim = sim

    def _show(self, text):
        self._sim.event("display", text=str(text)[:40])

    def text(self, text, on=500, off=50):
        text = str(text)
        self._show(text)
        self._sim.advance(len(text) * (number(on, "on", "text") + number(off, "off", "text")))

    def number(self, number_):
        self._show(number_)

    def char(self, char):
        self._show(str(char)[:1])

    def icon(self, icon):
        self._show(repr(icon))

    def off(self):
        self._show("")

    def pixel(self, row, column, brightness=100):
        pass

    def orientation(self, up):
        pass

    def animate(self, matrices, interval):
        pass


_NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _note(note, tempo):
    """Parse a Pybricks note like 'C4/4', 'F#5/8.' or 'R/2' into (frequency, ms)."""
    match = re.fullmatch(r"([A-GR])([#b]?)(\d?)/(\d+)(\.?)(_?)", note.strip())
    if not match:
        raise ValueError(f"invalid note '{note}'")
    letter, accidental, octave, fraction, dotted, _ = match.groups()
    whole = 4 * 60000 / tempo
    ms = whole / int(fraction) * (1.5 if dotted else 1)
    if letter == "R":
        return 0, ms
    semitone = _NOTE_OFFSETS[letter] + (1 if accidental == "#" else -1 if accidental == "b" else 0)
    midi = 12 * (int(octave or 4) + 1) + semitone
    return round(440 * 2 ** ((midi - 69) / 12)), ms


class _Speaker:
    def __init__(self, sim):
        self._sim = sim
        self._volume = 100

    def beep(self, frequency=500, duration=100):
        frequency = number(frequency, "frequency", "beep")
        duration = number(duration, "duration", "beep")
        self._sim.event("beep", frequency=round(frequency), duration=round(max(duration, 0)))
        self._sim.advance(max(duration, 0))

    def play_notes(self, notes, tempo=120):
        tempo = number(tempo, "tempo", "play_notes")
        for note in notes:
            frequency, ms = _note(str(note), tempo)
            if frequency:
                self._sim.event("beep", frequency=frequency, duration=round(ms * 0.9))
            self._sim.advance(ms)

    def volume(self, volume=None):
        if volume is None:
            return self._volume
        self._volume = int(number(volume, "volume", "volume"))


class _Buttons:
    def __init__(self, sim):
        self._sim = sim

    def pressed(self):
        return self._sim.pressed_buttons()


class _System:
    def set_stop_button(self, button):
        pass

    def name(self):
        return "Trainer Bot"

    def reset_reason(self):
        return 0

    def shutdown(self):
        raise SystemExit

    def storage(self, *args, **kwargs):
        raise NotInSimulator("hub.system.storage()")


class _Battery:
    def voltage(self):
        return 8200

    def current(self):
        return 150


class PrimeHub:
    """The SPIKE Prime hub: gyro, lights, display, speaker and buttons."""

    def __init__(self, top_side=Side.TOP, front_side=Side.FRONT, broadcast_channel=None, observe_channels=()):
        sim = current()
        self.imu = _IMU(sim)
        self.light = _Light(sim)
        self.display = _Display(sim)
        self.speaker = _Speaker(sim)
        self.buttons = _Buttons(sim)
        self.system = _System()
        self.battery = _Battery()

    def __repr__(self):
        return "PrimeHub()"


InventorHub = PrimeHub
