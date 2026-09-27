"""Check one lesson in a separate process: python -m trainer_content.check

Reads JSON from stdin: {"lesson": {...}, "robot": {...}, "worlds": {...},
"playground": {...}} and prints a JSON list of problems. The backend uses
this so that lesson code written by teachers never runs inside the web
server, and a runaway program can be stopped with a timeout.
"""

import json
import sys
from types import SimpleNamespace

from trainer_content import Checker, ContentError, resolve_blocks


def main():
    request = json.load(sys.stdin)
    library = SimpleNamespace(
        robot=request["robot"],
        worlds=request["worlds"],
        playground_by_id=request.get("playground", {}),
    )
    try:
        lesson = resolve_blocks(request["lesson"], library.playground_by_id)
        problems = Checker(library, run=request.get("run", True)).check_lesson(lesson)
    except ContentError as error:
        problems = [str(error)]
    except Exception as error:  # a broken lesson must never crash the checker
        problems = [f"the lesson couldn't be checked: {error}"]
    json.dump(problems, sys.stdout)


if __name__ == "__main__":
    main()
