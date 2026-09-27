"""Who can see whose work. This is the one place the rule lives, so the
coach app (later) only needs new screens, not new data rules.

- Everyone can see their own work.
- Coaches and mentors can see the students on their teams.
- Staff (site admins) can see everyone.
"""

from .models import Membership

LEADER_ROLES = (Membership.Role.COACH, Membership.Role.MENTOR)


def leads_team(user, team):
    return user.is_authenticated and (
        user.is_staff or Membership.objects.filter(user=user, team=team, role__in=LEADER_ROLES).exists()
    )


def can_view_student(viewer, student):
    if not viewer.is_authenticated:
        return False
    if viewer == student or viewer.is_staff:
        return True
    led_teams = Membership.objects.filter(user=viewer, role__in=LEADER_ROLES).values("team")
    return Membership.objects.filter(user=student, team__in=led_teams, role=Membership.Role.STUDENT).exists()


def sees_solutions(user):
    """Coaches, mentors and staff can see challenge solutions."""
    return user.is_authenticated and (
        user.is_staff or Membership.objects.filter(user=user, role__in=LEADER_ROLES).exists()
    )
