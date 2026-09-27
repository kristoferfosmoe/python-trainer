"""The lesson checker service: python -m trainer_content.server <socket path>

In production it runs in its own container with no network, no secrets and
a read-only disk (deploy/docker-compose.yml). Django sends it lessons over
a Unix socket in a volume the two containers share, so lesson code written
in the admin never runs where the database password is.

Protocol: the client sends the JSON that trainer_content.check reads, plus
an optional "timeout" (seconds), then closes its side of the connection.
The server answers {"problems": [...]}. An empty request is a health check.
"""

import json
import os
import socketserver
import sys
import threading

from .sandbox import run_check

MAX_REQUEST = 16 * 1024 * 1024
DEFAULT_TIMEOUT = 90
MAX_TIMEOUT = 600
# Each check is a Python process of its own; don't let a burst of saves
# start more than a few at once.
running = threading.BoundedSemaphore(2)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        data = self.rfile.read(MAX_REQUEST + 1)
        if not data:
            return
        if len(data) > MAX_REQUEST:
            problems = ["The lesson is too big to check."]
        else:
            try:
                request = json.loads(data)
                timeout = min(float(request.pop("timeout", DEFAULT_TIMEOUT)), MAX_TIMEOUT)
            except (ValueError, TypeError, AttributeError):
                problems = ["The lesson checker got a request it couldn't read."]
            else:
                with running:
                    problems = run_check(json.dumps(request), timeout)
        self.wfile.write(json.dumps({"problems": problems}).encode())


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def serve(path):
    """A server listening on `path` (call serve_forever() on it)."""
    if os.path.exists(path):
        os.unlink(path)  # left over from the last run
    return Server(path, Handler)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m trainer_content.server <socket path>")
    server = serve(sys.argv[1])
    print(f"Lesson checker listening on {sys.argv[1]}", file=sys.stderr, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
