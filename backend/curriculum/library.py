"""The database's content, shaped like trainer_content.Library, plus lesson
checks that run in a separate process."""

import json
import socket

from django.conf import settings
from trainer_content.sandbox import TOO_LONG, run_check

from .models import PlaygroundChallenge, Robot, World


class DatabaseLibrary:
    def __init__(self):
        robot = Robot.objects.order_by("id").first()
        self.robot = robot.spec if robot else {}
        self.worlds = {w.slug: w.spec for w in World.objects.all()}
        self.playground_by_id = {c.slug: c.spec for c in PlaygroundChallenge.objects.all()}


NO_CHECKER = "The lesson checker isn't running, so the lesson couldn't be checked. Try again in a minute."
MAX_ANSWER = 1024 * 1024


def check_lesson(lesson, library=None, run=True):
    """Problems with a lesson (a list of strings; empty means it's fine).

    Lesson code written in the admin never runs inside the web server. In
    production it runs in the checker container, which has no network, no
    secrets and a read-only disk (trainer_content.server). Without one, as
    in development, it runs in a limited process on this computer.
    """
    library = library or DatabaseLibrary()
    request = {
        "lesson": lesson,
        "robot": library.robot,
        "worlds": library.worlds,
        "playground": library.playground_by_id,
        "run": run,
    }
    if settings.LESSON_CHECKER_SOCKET:
        return _ask_checker(request)
    if settings.PRODUCTION:
        # Never run lesson code next to the site's secrets.
        return [NO_CHECKER]
    return run_check(json.dumps(request), settings.LESSON_CHECK_TIMEOUT)


def _ask_checker(request):
    timeout = settings.LESSON_CHECK_TIMEOUT
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            # The checker stops the lesson at `timeout`; allow for waiting in line.
            conn.settimeout(timeout * 2 + 15)
            conn.connect(settings.LESSON_CHECKER_SOCKET)
            conn.sendall(json.dumps({**request, "timeout": timeout}).encode())
            conn.shutdown(socket.SHUT_WR)
            answer = b""
            while chunk := conn.recv(65536):
                answer += chunk
                if len(answer) > MAX_ANSWER:
                    return ["The lesson checker's answer was too big."]
    except TimeoutError:
        return [TOO_LONG]
    except OSError:
        return [NO_CHECKER]
    try:
        return list(json.loads(answer)["problems"])
    except (ValueError, KeyError, TypeError):
        return [NO_CHECKER]
