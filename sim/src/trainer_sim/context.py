"""The simulation that's running right now (the pybricks modules look it up)."""

_current = None


def current():
    if _current is None:
        raise RuntimeError("The robot simulator isn't running.")
    return _current


def set_current(sim):
    global _current
    _current = sim
