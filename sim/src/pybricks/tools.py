"""Simulated ``pybricks.tools``: wait() and StopWatch."""

from trainer_sim.context import current
from trainer_sim.errors import NotInSimulator

from ._args import number


def wait(time):
    """Pause the program for `time` milliseconds. The robot keeps doing what it was doing."""
    current().advance(max(0.0, number(time, "time", "wait")))


class StopWatch:
    """Measures time in milliseconds."""

    def __init__(self):
        self._sim = current()
        self._start = self._sim.now
        self._paused_at = None

    def time(self):
        end = self._paused_at if self._paused_at is not None else self._sim.now
        return int(end - self._start)

    def pause(self):
        if self._paused_at is None:
            self._paused_at = self._sim.now

    def resume(self):
        if self._paused_at is not None:
            self._start += self._sim.now - self._paused_at
            self._paused_at = None

    def reset(self):
        self._start = self._sim.now
        if self._paused_at is not None:
            self._paused_at = self._sim.now


def multitask(*args, **kwargs):
    raise NotInSimulator("multitask()")


def run_task(*args, **kwargs):
    raise NotInSimulator("run_task()")


def hub_menu(*args, **kwargs):
    raise NotInSimulator("hub_menu()")


def read_input_byte(*args, **kwargs):
    raise NotInSimulator("read_input_byte()")
