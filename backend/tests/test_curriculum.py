import shutil

import pytest
import yaml
from django.core.management import CommandError, call_command
from django.test import Client

from accounts.models import User
from curriculum.admin import LessonForm, WorldForm
from curriculum.models import Course, Lesson, PlaygroundChallenge, Unit, World
from teams.models import Membership

from .conftest import make_user

pytestmark = pytest.mark.django_db


def test_import_loaded_everything():
    assert World.objects.count() >= 6
    assert PlaygroundChallenge.objects.count() == 7
    assert Lesson.objects.count() >= 12
    first = Lesson.objects.first()
    assert first.slug == "hello-python"
    assert first.content["blocks"][0]["type"] == "text"


def test_reimport_updates_in_place():
    before = {lesson.slug: lesson.version for lesson in Lesson.objects.all()}
    call_command("import_content", "--no-check", verbosity=0)
    after = {lesson.slug: lesson.version for lesson in Lesson.objects.all()}
    assert before == after  # nothing changed, so no new versions


def test_editing_a_lesson_bumps_its_version():
    lesson = Lesson.objects.get(slug="for-loops")
    lesson.title = "New title"
    lesson.save()
    assert lesson.version == 1
    lesson.content = {**lesson.content, "concepts": ["loops"]}
    lesson.save()
    assert lesson.version == 2


def test_import_refuses_broken_content(tmp_path, settings):
    content = tmp_path / "content"
    shutil.copytree(settings.CONTENT_DIR, content)
    path = content / "courses/fll-python/01-meet-the-robot/01-hello-python.yaml"
    lesson = yaml.safe_load(path.read_text())
    lesson["blocks"].append({"type": "example", "code": "print(1 / 0)"})
    path.write_text(yaml.safe_dump(lesson))
    title = Lesson.objects.get(slug="hello-python").title
    with pytest.raises(CommandError, match="ZeroDivisionError"):
        call_command("import_content", "--path", str(content), verbosity=0)
    assert Lesson.objects.get(slug="hello-python").content["blocks"][-1]["type"] == "challenge"
    assert Lesson.objects.get(slug="hello-python").title == title


def test_catalog_for_guests_has_no_solutions():
    data = Client().get("/api/catalog").json()
    assert data["solutions_included"] is False
    assert all("solution" not in c for c in data["playground"])
    assert data["robot"]["id"] == "trainer-bot"
    lessons = [lesson["id"] for unit in data["courses"][0]["units"] for lesson in unit["lessons"]]
    assert lessons[0] == "hello-python"
    assert "blocks" not in data["courses"][0]["units"][0]["lessons"][0]


def test_lesson_hides_solutions_from_students(student, coach, client_for):
    guest = Client().get("/api/lessons/for-loops").json()
    challenge = guest["blocks"][-1]
    assert challenge["id"] == "square-dance" and challenge["world"] == "practice-field"
    assert "solution" not in challenge
    assert "solution" not in client_for(student).get("/api/lessons/for-loops").json()["blocks"][-1]
    assert "solution" in client_for(coach).get("/api/lessons/for-loops").json()["blocks"][-1]
    assert client_for(coach).get("/api/catalog").json()["solutions_included"] is True


def test_unpublished_lessons_are_for_staff_only(student, client_for):
    Lesson.objects.filter(slug="turning").update(published=False)
    assert Client().get("/api/lessons/turning").status_code == 404
    assert client_for(student).get("/api/lessons/turning").status_code == 404
    staff = make_user("staffer", kind=User.Kind.ADULT, is_staff=True)
    assert client_for(staff).get("/api/lessons/turning").status_code == 200
    guest_lessons = [
        lesson["id"] for unit in Client().get("/api/catalog").json()["courses"][0]["units"] for lesson in unit["lessons"]
    ]
    assert "turning" not in guest_lessons


def test_team_courses_are_only_for_the_team(student, team, client_for):
    course = Course.objects.create(slug="team-extras", title="Team extras", owner_team=team)
    unit = Unit.objects.create(course=course, slug="u", title="Extras")
    Lesson.objects.create(unit=unit, slug="secret-lesson", title="Secret", summary="Just us",
                          content={"blocks": [{"type": "text", "markdown": "Hi team"}]})
    titles = lambda client: [c["title"] for c in client.get("/api/catalog").json()["courses"]]  # noqa: E731
    assert "Team extras" not in titles(Client())
    assert "Team extras" not in titles(client_for(student))
    Membership.objects.create(user=student, team=team)
    assert "Team extras" in titles(client_for(student))
    assert client_for(student).get("/api/lessons/secret-lesson").status_code == 200
    assert Client().get("/api/lessons/secret-lesson").status_code == 404


def lesson_form(blocks_yaml, slug="new-lesson"):
    unit = Unit.objects.first()
    return LessonForm(data={
        "unit": unit.pk, "slug": slug, "title": "New lesson", "summary": "Testing", "order": 9,
        "published": True, "content_yaml": blocks_yaml,
    })


def test_admin_lesson_form_accepts_a_good_lesson():
    form = lesson_form("""
blocks:
  - type: text
    markdown: Hello
  - type: challenge
    ref: first-drive
""")
    assert form.is_valid(), form.errors
    lesson = form.save()
    assert lesson.content["blocks"][1] == {"type": "challenge", "ref": "first-drive"}


def test_admin_lesson_form_rejects_problems():
    form = lesson_form("""
blocks:
  - type: quiz
    question: What is 2 + 2?
    check: output
    code: print(2 + 2)
    choices: ["3", "4"]
    answer: 0
  - type: challenge
    world: practice-field
    starter: "x = 1"
    solution: "x = 2"
    goals: [{type: end_in_zone, zone: garage}]
""")
    assert not form.is_valid()
    errors = " ".join(form.non_field_errors())
    assert "the code prints '4', but the answer is '3'" in errors
    assert "the solution fails" in errors


def test_admin_lesson_form_rejects_bad_yaml():
    form = lesson_form("blocks: [unclosed")
    assert not form.is_valid()
    assert "isn't valid YAML" in " ".join(form.non_field_errors())


def test_admin_stops_lessons_that_never_end(settings):
    # One line of built-in work never gives the simulator's time limit a
    # chance to fire, so the checker's own timeout has to stop it.
    settings.LESSON_CHECK_TIMEOUT = 3
    form = lesson_form("""
blocks:
  - type: example
    code: |
      total = sum(range(10 ** 12))
""")
    assert not form.is_valid()
    assert "took too long" in " ".join(form.non_field_errors())


def test_admin_world_form_checks_the_world():
    form = WorldForm(data={"slug": "bad", "name": "Bad", "spec_yaml": "shapes: [{type: rect, x: 0, y: 0, w: 5, h: 5, color: plaid}]"})
    assert not form.is_valid()
    assert "plaid" in " ".join(form.non_field_errors())


def test_admin_pages_load():
    admin = make_user("site_admin", kind=User.Kind.ADULT, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    lesson = Lesson.objects.get(slug="for-loops")
    for url in [
        "/admin/", "/admin/curriculum/lesson/", f"/admin/curriculum/lesson/{lesson.pk}/change/",
        "/admin/curriculum/world/", "/admin/teams/team/", "/admin/accounts/user/", "/admin/progress/attempt/",
    ]:
        assert client.get(url).status_code == 200, url


def test_lessons_remember_their_file():
    lesson = Lesson.objects.get(slug="for-loops")
    assert lesson.source == "content/courses/fll-python/04-loops/01-for-loops.yaml"
    form = LessonForm(instance=lesson)
    assert "comes from content/courses/fll-python/04-loops/01-for-loops.yaml" in form.fields["content_yaml"].help_text


def test_health():
    assert Client().get("/api/health").json() == {"ok": True}


def test_admin_yaml_is_readable_and_round_trips():
    from curriculum.admin import dump_yaml

    for lesson in Lesson.objects.all():
        text = dump_yaml(lesson.content)
        assert yaml.safe_load(text) == lesson.content, lesson.slug
    text = dump_yaml(Lesson.objects.get(slug="for-loops").content)
    assert "markdown: |" in text and "code: |" in text
