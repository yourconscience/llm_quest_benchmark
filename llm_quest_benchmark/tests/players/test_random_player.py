from llm_quest_benchmark.players.random import RandomPlayer


def test_random_player_replaces_prior_auto_single_response():
    player = RandomPlayer(seed=7, skip_single=True)

    assert player.get_action("intro", [{"id": "1", "text": "Continue"}]) == 1
    assert player.get_last_response().is_default is True

    action = player.get_action(
        "decision",
        [
            {"id": "2", "text": "Left"},
            {"id": "3", "text": "Right"},
        ],
    )

    response = player.get_last_response()
    assert response.action == action
    assert response.is_default is False
    assert response.reasoning is None
