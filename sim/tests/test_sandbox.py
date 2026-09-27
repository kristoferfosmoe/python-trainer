"""The lesson checker's process limits and its service (trainer_content.sandbox
and trainer_content.server). Lesson code from the admin runs there."""

import json
import os
import socket
import threading

import pytest

from trainer_content.sandbox import run_check
from trainer_content.server import MAX_REQUEST, serve

from conftest import CONTENT, load

# The simulator's import rules are not a sandbox: this reaches the os module.
ESCAPE = "os = [c for c in ().__class__.__base__.__subclasses__() if c.__name__ == '_wrap_close'][0].__init__.__globals__\n"

posix_only = pytest.mark.skipif(os.name != "posix", reason="needs POSIX resource limits")


def request_for(code):
    worlds = {path.stem: load("worlds", path.stem) for path in (CONTENT / "worlds").glob("*.yaml")}
    return {
        "lesson": {"id": "sneaky", "title": "Sneaky", "summary": "x", "blocks": [{"type": "example", "code": code}]},
        "robot": load("robots", "trainer-bot"),
        "worlds": worlds,
        "playground": {},
    }


def check(code, timeout=30):
    return run_check(json.dumps(request_for(code)), timeout)


def test_a_fine_lesson_has_no_problems():
    assert check("print('hello')") == []


@posix_only
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root isn't held to the process limit")
def test_lesson_code_cant_start_programs(tmp_path):
    ran = tmp_path / "ran"
    problems = check(ESCAPE + f"os['system']('touch {ran}')\nos['fork']()")
    assert not ran.exists()
    assert len(problems) == 1
    assert "Resource temporarily unavailable" in problems[0]


@posix_only
def test_lesson_code_cant_write_files(tmp_path):
    target = tmp_path / "planted.txt"
    problems = check(ESCAPE + f"fd = os['open']({str(target)!r}, os['O_WRONLY'] | os['O_CREAT'])\nos['write'](fd, b'x')")
    assert len(problems) == 1
    assert "File too large" in problems[0]
    assert not target.exists() or target.stat().st_size == 0


@pytest.fixture
def server(tmp_path):
    path = str(tmp_path / "checker.sock")
    server = serve(path)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield path
    server.shutdown()
    server.server_close()


def ask(path, data):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(60)
        conn.connect(path)
        conn.sendall(data)
        conn.shutdown(socket.SHUT_WR)
        answer = b""
        while chunk := conn.recv(65536):
            answer += chunk
    return answer


def test_the_service_checks_lessons(server):
    good = json.loads(ask(server, json.dumps(request_for("print(1)")).encode()))
    assert good == {"problems": []}
    bad = json.loads(ask(server, json.dumps(request_for("print(1")).encode()))
    assert "SyntaxError" in bad["problems"][0]


def test_the_service_answers_health_checks_and_bad_requests(server):
    assert ask(server, b"") == b""
    assert "couldn't read" in json.loads(ask(server, b"not json"))["problems"][0]
    assert "too big" in json.loads(ask(server, b"x" * (MAX_REQUEST + 10)))["problems"][0]


def test_the_service_uses_the_requested_timeout(server):
    request = {**request_for("total = sum(range(10 ** 12))"), "timeout": 1}
    assert "took too long" in json.loads(ask(server, json.dumps(request).encode()))["problems"][0]
