"""Make a coach account (an adult with a password), optionally with a team.

    python manage.py create_coach coach_kim --team "Brick Builders" --season 2026-27

Asks for the password unless --password is given. Running it again for the
same username changes the password and adds the team.
"""

import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from teams.models import Membership, Team


class Command(BaseCommand):
    help = "Make a coach account, and optionally a team they coach."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--password", help="Otherwise you'll be asked for it.")
        parser.add_argument("--team", help="Team name. The team is made if it doesn't exist yet.")
        parser.add_argument("--season", default="", help="For a new team, e.g. 2026-27.")

    def handle(self, username, password=None, team=None, season="", **options):
        user = User.objects.filter(username__iexact=username).first()
        if user and user.kind != User.Kind.ADULT:
            raise CommandError(f"{user.username} is a student account, not a coach.")
        if password is None:
            password = getpass.getpass("Password: ")
            if password != getpass.getpass("Password (again): "):
                raise CommandError("The passwords don't match.")
        try:
            validate_password(password, user or User(username=username, kind=User.Kind.ADULT))
        except ValidationError as error:
            raise CommandError(" ".join(error.messages))

        with transaction.atomic():
            if user is None:
                user = User.objects.create_user(username=username, password=password, kind=User.Kind.ADULT)
                self.stdout.write(f"Made coach account {user.username}.")
            else:
                user.set_password(password)
                user.save(update_fields=["password"])
                self.stdout.write(f"Changed the password for {user.username}.")
            if team:
                found = Team.objects.filter(name__iexact=team).first()
                if found is None:
                    found = Team.objects.create(name=team, season=season, created_by=user)
                    self.stdout.write(f"Made team {found.name} (join code {found.join_code}).")
                Membership.objects.update_or_create(user=user, team=found, defaults={"role": Membership.Role.COACH})
                self.stdout.write(f"{user.username} coaches {found.name}.")
