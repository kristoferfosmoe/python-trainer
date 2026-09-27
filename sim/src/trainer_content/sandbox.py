"""Run one lesson check (trainer_content.check) in a separate, limited process.

Lesson code written in the admin is real Python, and the simulator's import
rules don't stop a determined author, so the check gets its own process
with a timeout and these limits:

- CPU time and memory, so a runaway lesson can't hog the server.
- No new processes, so the code can't run shell commands.
- No writing to files.

In production this runs inside the checker container (trainer_content.server),
which adds the real walls: no network, no secrets and a read-only disk.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SIM_SRC = Path(__file__).resolve().parents[1]
MEMORY_LIMIT = 1536 * 1024 * 1024

TOO_LONG = "Checking the lesson took too long. Is there a loop that never ends?"


def _limits(cpu_seconds):
    def apply():
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))

    return apply


def run_check(payload, timeout):
    """Check a lesson and return its problems (a list of strings; empty means it's fine).

    `payload` is the JSON that trainer_content.check reads.
    """
    env = {
        "PYTHONPATH": str(SIM_SRC),
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    # A backstop: the wall-clock timeout should stop the checker first. If
    # the CPU limit were the same, the two would race.
    limits = _limits(int(timeout) + 5) if os.name == "posix" else None
    try:
        result = subprocess.run(
            [sys.executable, "-B", "-m", "trainer_content.check"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            preexec_fn=limits,
        )
    except subprocess.TimeoutExpired:
        return [TOO_LONG]
    if result.returncode < 0:
        # Killed by a signal: the CPU limit above.
        return [TOO_LONG]
    if result.returncode != 0:
        return [f"The lesson checker crashed: {result.stderr.strip()[-600:]}"]
    return json.loads(result.stdout)
