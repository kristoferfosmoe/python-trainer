"""Argument checks that give students clear messages instead of deep tracebacks."""

import math

from trainer_sim.errors import ArgumentError, ArgumentValueError

from .parameters import Stop


def number(value, name, func):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        extra = " Remove the quotes: text in quotes isn't a number." if isinstance(value, str) else ""
        raise ArgumentError(
            f"{func}() expected a number for '{name}', but got {type(value).__name__} {value!r}",
            f"`{func}()` needs a number for {name}, but got `{value!r}`.{extra}",
        )
    if math.isnan(value) or math.isinf(value):
        raise ArgumentValueError(
            f"{func}() got {value!r} for '{name}'",
            f"`{func}()` needs a normal number for {name}, not `{value!r}`.",
        )
    return float(value)


def positive(value, name, func):
    value = number(value, name, func)
    if value <= 0:
        raise ArgumentValueError(
            f"{func}() expected a positive value for '{name}', got {value:g}",
            f"`{func}()` needs {name} to be more than 0.",
        )
    return value


def stop(value, func):
    if not isinstance(value, Stop):
        raise ArgumentError(
            f"{func}() expected a Stop value for 'then', got {value!r}",
            f"`then=` needs a Stop value, like `Stop.HOLD`, `Stop.BRAKE` or `Stop.COAST`.",
        )
    return value


def flag(value, name, func):
    if not isinstance(value, bool):
        raise ArgumentError(
            f"{func}() expected True or False for '{name}', got {value!r}",
            f"`{name}=` must be `True` or `False`.",
        )
    return value
