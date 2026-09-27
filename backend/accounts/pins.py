"""Rules for usernames and PINs. Messages are written for kids."""

import random
import re
import secrets

PIN_LENGTH = 6
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")
RESERVED = {"admin", "administrator", "root", "coach", "teacher", "staff", "support", "system"}


def username_problem(username):
    if not USERNAME_RE.match(username or ""):
        return "Usernames are 3 to 20 letters, numbers or _, and start with a letter."
    if username.lower() in RESERVED:
        return "That username is reserved. Please pick another one."
    return None


def pin_problem(pin):
    pin = pin or ""
    if len(pin) != PIN_LENGTH or not pin.isdigit():
        return f"Your PIN must be exactly {PIN_LENGTH} numbers."
    if len(set(pin)) == 1:
        return "That PIN is too easy to guess (all the same number). Try mixing it up."
    if pin in "0123456789012" or pin in "9876543210987":
        return "That PIN is too easy to guess (counting up or down). Try mixing it up."
    if pin[:3] == pin[3:] or pin[:2] * 3 == pin:
        return "That PIN is too easy to guess (it repeats). Try mixing it up."
    return None


ADJECTIVES = [
    "Brave", "Clever", "Speedy", "Mighty", "Happy", "Sneaky", "Rapid", "Shiny", "Lucky", "Bold",
    "Cosmic", "Turbo", "Quiet", "Jolly", "Swift", "Zippy", "Fuzzy", "Epic", "Nifty", "Sunny",
]
ANIMALS = [
    "Otter", "Falcon", "Panda", "Gecko", "Tiger", "Koala", "Robin", "Beaver", "Dolphin", "Lynx",
    "Moose", "Badger", "Heron", "Puffin", "Yak", "Llama", "Wombat", "Squid", "Bison", "Fox",
]


def suggest_username(rng=random):
    return f"{rng.choice(ADJECTIVES)}{rng.choice(ANIMALS)}{rng.randint(10, 99)}"


def random_pin(rng=secrets.SystemRandom()):
    """A PIN that's hard to guess (made with the system's secure random numbers)."""
    while True:
        pin = "".join(rng.choice("0123456789") for _ in range(PIN_LENGTH))
        if pin_problem(pin) is None:
            return pin
