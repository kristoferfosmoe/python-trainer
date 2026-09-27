"""The database's content, shaped like trainer_content.Library, plus lesson
checks that run in a separate process."""

import json
import os
import subprocess
import sys

from django.conf import settings

from .models import PlaygroundChallenge, Robot, World


class DatabaseLibrary:
    def __init__(self):
        robot = Robot.objects.order_by("id").first()
        self.robot = robot.spec if robot else {}
        self.worlds = {w.slug: w.spec for w in World.objects.all()}
        self.playground_by_id = {c.slug: c.spec for c in PlaygroundChallenge.objects.all()}


TOO_LONG = "Checking the lesson took too long. Is there a loop that never ends?"


def _limit_resources():
    import resource

    # A backstop: the wall-clock timeout in check_lesson() should stop the
    # checker first. If the CPU limit were the same, the two would race.
    seconds = settings.LESSON_CHECK_TIMEOUT + 5
    resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
    memory = 1536 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))


def check_lesson(lesson, library=None, run=True):
    """Problems with a lesson (a list of strings; empty means it's fine).

    Lesson code written in the admin runs in a separate process with a time
    and memory limit, never inside the web server.
    """
    library = library or DatabaseLibrary()
    payload = json.dumps({
        "lesson": lesson,
        "robot": library.robot,
        "worlds": library.worlds,
        "playground": library.playground_by_id,
        "run": run,
    })
    env = {"PYTHONPATH": str(settings.SIM_SRC), "PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "trainer_content.check"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=settings.LESSON_CHECK_TIMEOUT,
            env=env,
            preexec_fn=_limit_resources if os.name == "posix" else None,
        )
    except subprocess.TimeoutExpired:
        return [TOO_LONG]
    if result.returncode < 0:
        # Killed by a signal: the CPU limit above.
        return [TOO_LONG]
    if result.returncode != 0:
        return [f"The lesson checker crashed: {result.stderr.strip()[-600:]}"]
    return json.loads(result.stdout)
