"""Who can see whose work, and who can manage a team. This is the one place
the rules live.

- Everyone can see their own work.
- Coaches and mentors can see the students on their teams.
- Only coaches manage a team: its students' accounts and PINs, its join
  code and its robot. Mentors are older students, so they can look but not
  change anything.
- Staff (site admins) can see and manage everything.
"""

from .models import Membership

LEADER_ROLES = (Membership.Role.COACH, Membership.Role.MENTOR)


def leads_team(user, team):
    return user.is_authenticated and (
        user.is_staff or Membership.objects.filter(user=user, team=team, role__in=LEADER_ROLES).exists()
    )


def coaches_team(user, team):
    return user.is_authenticated and (
        user.is_staff or Membership.objects.filter(user=user, team=team, role=Membership.Role.COACH).exists()
    )


def can_view_student(viewer, student):
    if not viewer.is_authenticated:
        return False
    if viewer == student or viewer.is_staff:
        return True
    led_teams = Membership.objects.filter(user=viewer, role__in=LEADER_ROLES).values("team")
    return Membership.objects.filter(user=student, team__in=led_teams, role=Membership.Role.STUDENT).exists()


def can_manage_account(user):
    """Coaches may change kids' accounts, never an adult's or an admin's."""
    from accounts.models import User

    return user.kind == User.Kind.STUDENT and not user.is_staff and not user.is_superuser


def sees_solutions(user):
    """Coaches, mentors and staff can see challenge solutions."""
    return user.is_authenticated and (
        user.is_staff or Membership.objects.filter(user=user, role__in=LEADER_ROLES).exists()
    )
