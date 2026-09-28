"""Every Mission Mode game in content/missions/ must load and check out.

Each challenge's solution must earn all three stars (on every seed), and
its starter must run without errors and earn none. See trainer_content.missions.
"""

import pytest

from conftest import CONTENT
from trainer_content.missions import MissionChecker, load_games

GAMES = load_games(CONTENT)
CHALLENGES = [(game, challenge) for game in GAMES for challenge in game["challenges"]]


def test_there_is_a_game_with_every_tier():
    assert GAMES, "no games in content/missions/"
    for game in GAMES:
        tiers = {t["id"] for t in game["tiers"]}
        assert tiers == {c["tier"] for c in game["challenges"]}, f"{game['id']}: a tier has no challenges"


@pytest.mark.parametrize("game", GAMES, ids=[g["id"] for g in GAMES])
def test_game(game):
    assert MissionChecker(run=False).check_game({**game, "challenges": []}) == []


@pytest.mark.parametrize("game, challenge", CHALLENGES, ids=[f"{g['id']}/{c['id']}" for g, c in CHALLENGES])
def test_challenge(game, challenge):
    assert MissionChecker().check_challenge(game, challenge) == []


def test_challenges_are_in_tier_order():
    for game in GAMES:
        tiers = [c["tier"] for c in game["challenges"]]
        assert tiers == sorted(tiers), f"{game['id']}: challenge files must be in tier order"
