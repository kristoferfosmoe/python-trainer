"""Load (or update) worlds, the robot, playground challenges, courses and
Mission Mode games from the YAML files in content/. Everything is checked
first, and nothing is imported if anything has a problem.

    python manage.py import_content [--path ../content] [--no-check]
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from curriculum.models import Course, Lesson, PlaygroundChallenge, Robot, Unit, World
from missions.models import MissionChallenge, MissionGame


def _relative(path, root):
    try:
        return str(Path(path).relative_to(Path(root).parent))
    except ValueError:
        return str(path)


class Command(BaseCommand):
    help = "Import lessons, worlds, challenges and Mission Mode games from the content/ folder."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=str(settings.CONTENT_DIR))
        parser.add_argument("--no-check", action="store_true", help="Skip running every lesson's code first.")

    def handle(self, *args, path, no_check, **options):
        from trainer_content import Checker, ContentError, Library
        from trainer_content.missions import MissionChecker, game_spec, load_games

        try:
            library = Library(path)
            games = load_games(path)
        except (ContentError, OSError) as error:
            raise CommandError(f"Couldn't read {path}: {error}")

        if not no_check:
            checker = Checker(library)
            problems = []
            for course in library.courses:
                problems += checker.check_course(course)
            for lesson in library.lessons():
                problems += checker.check_lesson(lesson)
            for challenge in library.playground:
                problems += checker.check_lesson({
                    "id": f"playground/{challenge['id']}", "title": challenge["title"], "summary": "playground",
                    "blocks": [{**challenge, "type": "challenge"}],
                })
            mission_checker = MissionChecker()
            for game in games:
                problems += mission_checker.check_game(game)
            if problems:
                raise CommandError("Nothing was imported. Problems:\n" + "\n".join(f"  - {p}" for p in problems))

        counts = {"worlds": 0, "challenges": 0, "courses": 0, "lessons": 0, "games": 0, "missions": 0}
        with transaction.atomic():
            for slug, spec in library.worlds.items():
                World.objects.update_or_create(slug=slug, defaults={"name": spec.get("name", slug), "spec": spec})
                counts["worlds"] += 1
            Robot.objects.update_or_create(
                slug=library.robot["id"], defaults={"name": library.robot.get("name", "Robot"), "spec": library.robot},
            )
            for order, challenge in enumerate(library.playground):
                PlaygroundChallenge.objects.update_or_create(
                    slug=challenge["id"],
                    defaults={"title": challenge["title"], "order": order, "spec": challenge},
                )
                counts["challenges"] += 1
            for course_order, data in enumerate(library.courses):
                course, _ = Course.objects.update_or_create(
                    slug=data["id"],
                    defaults={"title": data["title"], "summary": data.get("summary", ""), "order": course_order},
                )
                counts["courses"] += 1
                for unit_order, unit_data in enumerate(data["units"]):
                    unit, _ = Unit.objects.update_or_create(
                        course=course, slug=unit_data["id"],
                        defaults={
                            "title": unit_data["title"], "icon": unit_data.get("icon", ""),
                            "summary": unit_data.get("summary", ""), "order": unit_order,
                        },
                    )
                    for lesson_order, raw in enumerate(unit_data["lessons"]):
                        content = {"concepts": raw.get("concepts", []), "blocks": raw["blocks"]}
                        lesson = Lesson.objects.filter(slug=raw["id"]).first() or Lesson(slug=raw["id"])
                        lesson.unit = unit
                        lesson.title = raw["title"]
                        lesson.summary = raw.get("summary", "")
                        lesson.order = lesson_order
                        lesson.content = content
                        lesson.source = _relative(raw.get("source", ""), library.root)
                        lesson.save()
                        counts["lessons"] += 1
            for game_order, game in enumerate(games):
                spec = game_spec(game)
                record, _ = MissionGame.objects.update_or_create(slug=game["id"], defaults={
                    "title": game["title"], "summary": game.get("summary", ""), "order": game_order, "spec": spec,
                    "source": _relative(game["source"], library.root),
                })
                counts["games"] += 1
                for order, challenge in enumerate(game["challenges"]):
                    source = _relative(challenge.pop("source", ""), library.root)
                    MissionChallenge.objects.update_or_create(slug=challenge["id"], defaults={
                        "game": record, "title": challenge["title"], "tier": challenge["tier"], "order": order,
                        "spec": challenge, "source": source,
                    })
                    counts["missions"] += 1
        self.stdout.write(self.style.SUCCESS(
            "Imported {worlds} worlds, {challenges} playground challenges, {courses} course(s), {lessons} lessons, "
            "{games} mission game(s) and {missions} mission challenges."
            .format(**counts)
        ))
