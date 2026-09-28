"""Scoring, like a referee reading the field: missions, precision tokens, goals and stars.

A game's score sheet lists missions. Each mission has scoring rules, checked
top to bottom; the first one that matches counts:

    missions:
      - id: M01
        title: Crate to the Dock
        score:
          - {when: {model: crate, in_zone: dock}, points: 20}
          - {when: {models: [box-1, box-2], in_zone: home}, points: 10, each: true}

Conditions in `when` (all must hold):
  model / models   which model(s) the rule is about
  state            a state name, or a list of them
  in_zone          the model's center is in this zone
  not_in_zone      ... and not in this one
  presses          a button was pressed at least this many times

Precision tokens: the team starts with some, loses one per interruption,
and the ones left are worth points at the end.
"""

from ..goals import check_goal
from ..shapes import ShapeError

CONDITION_KEYS = ("model", "models", "state", "in_zone", "not_in_zone", "presses")
MISSION_GOALS = ("mission_done", "min_score", "model_state", "model_in_zone")
DEFAULT_TOKENS = {"start": 6, "points": [0, 10, 15, 25, 35, 50, 50]}


def _as_list(value):
    return value if isinstance(value, list) else [value]


class Scorer:
    def __init__(self, missions, tokens, field, world, only=None):
        self.field = field
        self.world = world
        self.missions = []
        for mission in missions or []:
            if not isinstance(mission, dict) or not mission.get("id") or not isinstance(mission.get("score"), list):
                raise ShapeError(f"each mission needs an 'id' and a 'score' list: {mission}")
            if only is not None and mission["id"] not in only:
                continue
            names = self._models_named(mission)
            if only is None and not all(name in field.models for name in names):
                continue  # its models aren't on this challenge's field
            for rule in mission["score"]:
                self._check_rule(mission["id"], rule)
            self.missions.append(mission)
        tokens = tokens if tokens is not None else DEFAULT_TOKENS
        if tokens is False:
            tokens = {"start": 0, "points": [0]}
        self.token_start = int(tokens.get("start", 6))
        self.token_points = [int(p) for p in tokens.get("points", [0] * (self.token_start + 1))]
        if len(self.token_points) != self.token_start + 1:
            raise ShapeError("precision_tokens: 'points' needs one number for 0 tokens left, 1 left, ... up to 'start'")
        self.tokens = self.token_start
        self.timeline = []
        self._last_total = None

    @staticmethod
    def _models_named(mission):
        names = []
        for rule in mission["score"]:
            when = rule.get("when", {}) if isinstance(rule, dict) else {}
            names += _as_list(when.get("models", [])) + ([when["model"]] if "model" in when else [])
        return names

    def _check_rule(self, mission_id, rule):
        where = f"mission {mission_id}"
        if not isinstance(rule, dict) or not isinstance(rule.get("when"), dict) or "points" not in rule:
            raise ShapeError(f"{where}: each scoring rule is like {{when: {{...}}, points: 10}}")
        when = rule["when"]
        for key in when:
            if key not in CONDITION_KEYS:
                raise ShapeError(f"{where}: unknown condition '{key}'. Use: {', '.join(CONDITION_KEYS)}")
        names = _as_list(when.get("models", [])) + ([when["model"]] if "model" in when else [])
        if not names:
            raise ShapeError(f"{where}: a scoring rule needs 'model' or 'models'")
        for name in names:
            model = self.field.models.get(name)
            if model is None:
                raise ShapeError(f"{where}: no model called '{name}' on the field")
            for state in _as_list(when.get("state", [])):
                if state not in model.all_states():
                    raise ShapeError(f"{where}: {name} has no state '{state}' (it has {', '.join(model.all_states())})")
        for key in ("in_zone", "not_in_zone"):
            if key in when and when[key] not in self.world.zones:
                raise ShapeError(f"{where}: no zone called '{when[key]}'")

    # --- Reading the field ---------------------------------------------------------

    def _holds(self, name, when):
        model = self.field.models[name]
        if "state" in when and model.state not in _as_list(when["state"]):
            return False
        if "presses" in when and getattr(model, "presses", 0) < int(when["presses"]):
            return False
        if "in_zone" in when or "not_in_zone" in when:
            where = model.position()
            if where is None:
                return False
            if "in_zone" in when and not self.world.zones[when["in_zone"]].contains(*where):
                return False
            if "not_in_zone" in when and self.world.zones[when["not_in_zone"]].contains(*where):
                return False
        return True

    def mission_points(self, mission):
        for rule in mission["score"]:
            when = rule["when"]
            names = _as_list(when["models"]) if "models" in when else [when["model"]]
            count = sum(1 for name in names if self._holds(name, when))
            if rule.get("each"):
                if count:
                    return int(rule["points"]) * count
            elif count == len(names):
                return int(rule["points"])
        return 0

    def sheet(self):
        rows = [{"id": m["id"], "title": m.get("title", m["id"]), "points": self.mission_points(m)} for m in self.missions]
        return rows

    def token_score(self):
        return self.token_points[max(0, min(self.tokens, self.token_start))]

    def total(self):
        return sum(row["points"] for row in self.sheet()) + self.token_score()

    def lose_token(self):
        self.tokens = max(0, self.tokens - 1)
        self.update()

    def update(self, *args):
        total = self.total()
        if total != self._last_total:
            self._last_total = total
            self.timeline.append([round(self.field.sim.phys_t, 1), total])

    def to_dict(self):
        return {
            "total": self.total(),
            "missions": self.sheet(),
            "tokens": self.tokens,
            "token_start": self.token_start,
            "token_points": self.token_score(),
            "timeline": self.timeline,
        }

    # --- Goals -------------------------------------------------------------------------

    def check_goal(self, spec, index, recording, end, code, sim):
        kind = spec.get("type")
        if kind not in MISSION_GOALS:
            return check_goal(spec, index, self.world, recording, end, code, sim)
        goal_id = spec.get("id", f"goal-{index + 1}")
        label = spec.get("label")
        if kind == "mission_done":
            mission = next((m for m in self.missions if m["id"] == spec.get("mission")), None)
            if mission is None:
                raise ShapeError(f"mission_done: no mission '{spec.get('mission')}' on this field")
            points = self.mission_points(mission)
            need = int(spec.get("points", 1))
            title = f"{mission['id']}: {mission.get('title', mission['id'])}"
            label = label or (f"Score {title}" if "points" not in spec else f"Score {need} points for {title}")
            passed = points >= need
            detail = "" if passed else ("No points for this mission yet." if not points else f"You got {points}.")
        elif kind == "min_score":
            need = int(spec["points"])
            total = self.total()
            label = label or f"Score at least {need} points"
            passed = total >= need
            detail = "" if passed else f"You scored {total}."
        elif kind == "model_in_zone":
            model = self.field.models.get(spec.get("model"))
            if model is None:
                raise ShapeError(f"model_in_zone: no model '{spec.get('model')}' on this field")
            zone = self.world.zones.get(spec.get("zone"))
            if zone is None:
                raise ShapeError(f"model_in_zone: no zone '{spec.get('zone')}'")
            label = label or f"Get the {model.label} into {zone.label or zone.id}"
            where = model.position()
            passed = where is not None and zone.contains(*where)
            detail = "" if passed else "It isn't there."
        else:
            model = self.field.models.get(spec.get("model"))
            if model is None:
                raise ShapeError(f"model_state: no model '{spec.get('model')}' on this field")
            state = spec.get("state")
            if state not in model.all_states():
                raise ShapeError(f"model_state: {model.id} has no state '{state}'")
            label = label or f"{model.label}: {str(state).replace('_', ' ')}"
            passed = model.state == state
            detail = "" if passed else f"It's {model.state.replace('_', ' ')}."
        return {"id": goal_id, "type": kind, "label": label, "passed": bool(passed), "detail": detail}

    def check_goals(self, goals, recording, end, code, sim):
        ok = end["reason"] in ("finished", "time_limit")
        results = [{
            "id": "no-errors",
            "type": "no_errors",
            "label": "Program runs without errors",
            "passed": ok,
            "detail": "" if ok else "Fix the error first.",
        }]
        for index, spec in enumerate(goals or []):
            results.append(self.check_goal(spec, index, recording, end, code, sim))
        return results
