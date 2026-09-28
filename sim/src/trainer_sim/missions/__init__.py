"""Mission Mode: attachments, mission models, scoring and matches.

Lessons and the playground never use this package. ``run_mission`` runs a
student's program as a match on a game's field and returns the same trace
``run_program`` does, plus a ``mission`` section (models, attachments, runs,
score and stars). See docs/MISSION_MODE.md.
"""

from .match import run_mission, run_mission_json

__all__ = ["run_mission", "run_mission_json"]
