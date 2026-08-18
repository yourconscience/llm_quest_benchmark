"""Contract tests for the append-only, full-fidelity quest trajectory."""

from llm_quest_benchmark.harnesses.trajectory import (
    MAX_OUTPUT_CHARS,
    MAX_READ_COUNT,
    MAX_SEARCH_RESULTS,
    Trajectory,
    _coerce_positive_int,
)
from llm_quest_benchmark.schemas.state import AgentState


def _append_step(
    trajectory: Trajectory,
    observation: str,
    choices: list[str],
    selected_action: int,
    selected_choice: str,
) -> AgentState:
    expected_choice = choices[selected_action - 1] if 1 <= selected_action <= len(choices) else ""
    assert selected_choice == expected_choice
    return trajectory.append(
        AgentState(
            step=len(trajectory) + 1,
            location_id="test",
            observation=observation,
            choices=[{"text": choice} for choice in choices],
            action=str(selected_action),
            llm_response=None,
        )
    )


def _fill(trajectory: Trajectory, n: int) -> None:
    for i in range(1, n + 1):
        _append_step(
            trajectory,
            observation=f"Observation {i} with detail.",
            choices=[f"Choice {i}A", f"Choice {i}B"],
            selected_action=1,
            selected_choice=f"Choice {i}A",
        )


def test_append_retains_full_observation_and_choices_without_clipping():
    trajectory = Trajectory()
    long_observation = "You enter the hall. " * 60  # far beyond any prompt-window clip budget
    long_choice = "Investigate the strange machinery in the corner. " * 5

    step = _append_step(
        trajectory,
        observation=long_observation,
        choices=[long_choice, "Leave"],
        selected_action=1,
        selected_choice=long_choice,
    )

    assert step.step == 1
    assert step.observation == long_observation
    assert step.choices == [{"text": long_choice}, {"text": "Leave"}]
    assert step.action == "1"
    assert step.choices[0]["text"] == long_choice
    assert trajectory.recent(1)[0] is step

    read_output = trajectory.read(1, 1)
    assert long_observation.strip() in read_output
    assert long_choice in read_output


def test_append_preserves_insertion_order_and_increments_step():
    trajectory = Trajectory()
    _fill(trajectory, 3)

    assert len(trajectory) == 3
    recent = trajectory.recent(10)
    assert [s.step for s in recent] == [1, 2, 3]
    assert [s.observation for s in recent] == [
        "Observation 1 with detail.",
        "Observation 2 with detail.",
        "Observation 3 with detail.",
    ]


def test_recent_returns_a_mutable_collection_of_canonical_references():
    trajectory = Trajectory()
    first = _append_step(trajectory, "First.", ["A"], 1, "A")
    _append_step(trajectory, "Second.", ["B"], 1, "B")

    snapshot = trajectory.recent(10)
    assert snapshot[0] is first
    snapshot.clear()

    assert len(trajectory) == 2


def test_read_returns_consecutive_range_in_chronological_order():
    trajectory = Trajectory()
    _fill(trajectory, 5)

    output = trajectory.read(2, 3)

    assert "Step 2:" in output
    assert "Step 3:" in output
    assert "Step 4:" in output
    assert "Step 1:" not in output
    assert "Step 5:" not in output
    # Chronology: step 2's line appears before step 4's line.
    assert output.index("Step 2:") < output.index("Step 3:") < output.index("Step 4:")


def test_read_clamps_count_to_max_and_to_available_entries():
    trajectory = Trajectory()
    _fill(trajectory, MAX_READ_COUNT + 5)

    over_max = trajectory.read(1, MAX_READ_COUNT + 5)
    assert over_max.count("Step ") == MAX_READ_COUNT

    near_end_start = len(trajectory) - 1
    partial = trajectory.read(near_end_start, MAX_READ_COUNT)
    assert partial.count("Step ") == 2  # only 2 entries remain from this start


def test_read_with_realistic_observation_sizes_never_slices_an_entry():
    """Real quest observations run ~200-1500 chars (verified against a live Boat.qm
    run). MAX_OUTPUT_CHARS must be tuned against that scale, not toy-size text:
    typical-size steps should fit the full MAX_READ_COUNT; worst-case (every step
    near the observed max) must degrade by dropping whole trailing entries with an
    explicit count, never by slicing an entry's text mid-way."""
    trajectory = Trajectory()
    sizes = [250, 500, 900, 1200, 1500, 300, 1100, 800, 1500, 400, 1200, 600]
    for size in sizes:
        _append_step(trajectory, "x" * size, ["Choice A text here", "Choice B text here"], 1, "Choice A text here")

    typical = trajectory.read(1, MAX_READ_COUNT)
    assert typical.count("Step ") == MAX_READ_COUNT
    assert "omitted" not in typical

    worst_case = Trajectory()
    for _ in range(MAX_READ_COUNT + 4):
        _append_step(worst_case, "x" * 1500, ["Choice A text here", "Choice B text here"], 1, "Choice A text here")

    result = worst_case.read(1, MAX_READ_COUNT)
    shown = result.count("Step ")
    assert 1 <= shown < MAX_READ_COUNT  # degrades, but never to zero
    assert f"[{shown} of {MAX_READ_COUNT} steps shown" in result
    # Every shown entry is whole: each has a matching selected= suffix, none cut off mid-observation.
    entry_lines = [line for line in result.splitlines() if line.startswith("Step ")]
    assert len(entry_lines) == shown
    assert all(line.endswith("selected=1: Choice A text here") for line in entry_lines)


def test_read_rejects_invalid_ranges_with_explicit_errors():
    trajectory = Trajectory()
    _fill(trajectory, 3)

    assert trajectory.read(0, 1).startswith("error:")
    assert trajectory.read(-1, 1).startswith("error:")
    assert trajectory.read(1, 0).startswith("error:")
    assert trajectory.read(1, -1).startswith("error:")
    assert trajectory.read(4, 1).startswith("error:")  # start_step beyond recorded steps
    assert trajectory.read("not-a-number", 1).startswith("error:")


def test_coerce_positive_int_accepts_only_ints_and_integer_strings():
    assert _coerce_positive_int(5) == 5
    assert _coerce_positive_int(0) == 0
    assert _coerce_positive_int(-1) == -1  # syntactically valid; sign checked by callers
    assert _coerce_positive_int("5") == 5
    assert _coerce_positive_int(" 5 ") == 5
    assert _coerce_positive_int("-1") == -1
    assert _coerce_positive_int("05") == 5


def test_coerce_positive_int_rejects_bool_float_and_decimal_strings():
    assert _coerce_positive_int(True) is None
    assert _coerce_positive_int(False) is None
    assert _coerce_positive_int(1.5) is None
    assert _coerce_positive_int(2.0) is None  # whole-number float still rejected, not silently truncated
    assert _coerce_positive_int("1.5") is None
    assert _coerce_positive_int("2.0") is None
    assert _coerce_positive_int(None) is None
    assert _coerce_positive_int("five") is None
    assert _coerce_positive_int("") is None
    assert _coerce_positive_int([1]) is None


def test_read_rejects_non_integral_start_step_and_count():
    trajectory = Trajectory()
    _fill(trajectory, 3)

    # Valid: plain ints and integer-only strings.
    assert trajectory.read(1, 2).startswith("Step 1:")
    assert trajectory.read("1", "2").startswith("Step 1:")

    # Invalid: bool.
    assert trajectory.read(True, 1) == "error: start_step must be a positive integer"
    assert trajectory.read(1, True) == "error: count must be a positive integer"

    # Invalid: float, including a whole-number float -- never silently truncated via int().
    assert trajectory.read(1.0, 1) == "error: start_step must be a positive integer"
    assert trajectory.read(1, 2.0) == "error: count must be a positive integer"
    assert trajectory.read(1.5, 1) == "error: start_step must be a positive integer"
    assert trajectory.read(1, 1.5) == "error: count must be a positive integer"

    # Invalid: decimal strings.
    assert trajectory.read("1.0", 1) == "error: start_step must be a positive integer"
    assert trajectory.read(1, "1.5") == "error: count must be a positive integer"


def test_search_rejects_non_integral_limit():
    trajectory = Trajectory()
    _fill(trajectory, 3)

    # Valid: plain int, integer string, and the None default.
    assert not trajectory.search("observation", 2).startswith("error:")
    assert not trajectory.search("observation", "2").startswith("error:")
    assert not trajectory.search("observation", None).startswith("error:")

    # Invalid: bool, float (including whole-number), and decimal strings.
    assert trajectory.search("observation", True) == "error: limit must be a positive integer"
    assert trajectory.search("observation", 2.0) == "error: limit must be a positive integer"
    assert trajectory.search("observation", 1.5) == "error: limit must be a positive integer"
    assert trajectory.search("observation", "1.5") == "error: limit must be a positive integer"


def test_read_on_empty_trajectory_is_explicit_error():
    trajectory = Trajectory()
    assert trajectory.read(1, 1) == "error: no history recorded yet"


def test_search_on_empty_trajectory_is_explicit_error():
    trajectory = Trajectory()
    assert trajectory.search("anything", 3) == "error: no history recorded yet"


def test_search_rejects_empty_query():
    trajectory = Trajectory()
    _fill(trajectory, 2)
    assert trajectory.search("", 3) == "error: empty query"
    assert trajectory.search("   ", 3) == "error: empty query"


def test_search_rejects_query_with_no_searchable_tokens():
    trajectory = Trajectory()
    _fill(trajectory, 2)
    assert trajectory.search("??? !!!", 3) == "error: query has no searchable tokens"


def test_search_handles_no_match_query_deterministically_without_error():
    trajectory = Trajectory()
    _fill(trajectory, 3)

    result = trajectory.search("nonexistentword", 3)

    assert not result.startswith("error:")
    assert "no matches" in result


def test_search_ranking_is_deterministic_by_match_count_then_recency():
    trajectory = Trajectory()
    _append_step(trajectory, "A quiet corridor.", ["Wait"], 1, "Wait")  # step 1: matches neither token
    _append_step(
        trajectory, "Merchant mentions fuel is low.", ["Buy fuel", "Leave"], 1, "Buy fuel"
    )  # step 2: both tokens
    _append_step(trajectory, "Fuel gauge blinks red now.", ["Refuel"], 1, "Refuel")  # step 3: one token
    _append_step(
        trajectory, "A trader mentions urgent fuel needs.", ["Pay"], 1, "Pay"
    )  # step 4: one token, ties step 3

    result_first = trajectory.search("fuel merchant", 3)
    result_second = trajectory.search("fuel merchant", 3)

    assert result_first == result_second  # deterministic across repeated calls
    # Highest match-count entry first (step 2, both tokens); single-token ties
    # broken by recency (higher step first): step 4 before step 3.
    assert result_first.index("Step 2:") < result_first.index("Step 4:") < result_first.index("Step 3:")
    assert "Step 1:" not in result_first  # zero-match entry excluded


def test_search_limit_clamps_to_max_and_rejects_non_positive():
    trajectory = Trajectory()
    for i in range(MAX_SEARCH_RESULTS + 3):
        _append_step(trajectory, f"repeat token step {i}", ["A"], 1, "A")

    over_max = trajectory.search("token", MAX_SEARCH_RESULTS + 10)
    assert over_max.count("Step ") == MAX_SEARCH_RESULTS

    default_limit = trajectory.search("token", None)
    assert default_limit.count("Step ") == MAX_SEARCH_RESULTS

    assert trajectory.search("token", 0).startswith("error:")
    assert trajectory.search("token", -1).startswith("error:")


def test_search_matches_choices_and_selected_choice_text_too():
    trajectory = Trajectory()
    _append_step(trajectory, "Unrelated scene.", ["Open the vault door"], 1, "Open the vault door")

    result = trajectory.search("vault", 3)

    assert "Step 1:" in result
    assert "vault" in result.lower()


def test_search_does_not_match_short_token_as_substring_of_longer_word():
    """A short query token like 'he' must not match merely because it
    appears as a substring inside a longer word like 'the' or 'chest'."""
    trajectory = Trajectory()
    _append_step(trajectory, "The old chest sits in the corner.", ["Wait"], 1, "Wait")

    result = trajectory.search("he", 3)

    assert not result.startswith("error:")
    assert "no matches" in result
    assert "Step 1:" not in result


def test_search_matches_short_token_only_as_a_whole_word():
    """The same short token must still match when it appears as an actual
    standalone word, proving the fix isn't just refusing all short tokens."""
    trajectory = Trajectory()
    _append_step(trajectory, "The old chest sits in the corner.", ["Wait"], 1, "Wait")  # no standalone 'he' token
    _append_step(trajectory, "He opens the heavy door.", ["Enter"], 1, "Enter")  # 'He' is a standalone token

    result = trajectory.search("he", 3)

    assert not result.startswith("error:")
    assert "Step 2:" in result
    assert "Step 1:" not in result  # 'the'/'chest' substrings must not count as a match


def test_single_oversized_entry_is_hard_bounded_not_returned_in_full():
    """A single entry larger than MAX_OUTPUT_CHARS must still yield a result
    <= MAX_OUTPUT_CHARS: only the FORMATTED output is truncated (with a clear
    marker), the stored canonical AgentState itself is never touched."""
    trajectory = Trajectory()
    huge_observation = "x" * (MAX_OUTPUT_CHARS * 2)
    _append_step(trajectory, huge_observation, ["A"], 1, "A")

    # Stored, full-fidelity entry is never truncated.
    assert trajectory.recent(1)[0].observation == huge_observation

    output = trajectory.read(1, 1)
    assert len(output) <= MAX_OUTPUT_CHARS  # hard bound, no exceptions
    assert huge_observation not in output  # formatted output was truncated
    assert "entry truncated, exceeds character budget" in output


def test_first_entry_near_full_budget_plus_second_entry_never_silently_slices():
    """Regression: a first formatted entry just below MAX_OUTPUT_CHARS, plus a
    second entry that cannot also fit, used to be admitted whole and then
    retroactively sliced (with no truncation marker) to make room for the
    trailing omission marker -- silently claiming "1 of 2 shown" while the one
    shown entry was actually partial. The first entry must now either be
    genuinely whole (if it plus the omission marker fits) or explicitly
    marked as truncated; it must never be silently cut."""
    trajectory = Trajectory()
    first_observation = "y" * 7900  # formatted line ~7948 chars: just below MAX_OUTPUT_CHARS
    _append_step(trajectory, first_observation, ["A"], 1, "A")
    _append_step(trajectory, "small second entry", ["B"], 1, "B")

    result = trajectory.read(1, 2)

    assert len(result) <= MAX_OUTPUT_CHARS  # hard bound, no exceptions
    assert "entry truncated, exceeds character budget" in result  # first entry was marked, not silently cut
    assert "[1 of 2 steps shown; remaining omitted, character budget]" in result
    # No unmarked partial entry: the only content before the entry-truncation
    # marker is a contiguous prefix of the real first observation, and the
    # full (untruncated) observation text never appears verbatim.
    assert first_observation not in result
    # Stored history is untouched regardless of what the formatted output did.
    assert trajectory.recent(2)[0].observation == first_observation


def test_output_omits_whole_trailing_entries_once_budget_is_exceeded():
    """Once a second whole entry would exceed the character budget, it (and any
    further requested entries) are dropped as whole entries, with an explicit,
    accurate count, never a mid-entry character slice. Each entry here fits
    comfortably alone, so this exercises entry-dropping, not entry-truncation."""
    trajectory = Trajectory()
    for _ in range(3):
        _append_step(trajectory, "y" * 3800, ["A"], 1, "A")  # ~3848 chars formatted, 2 fit in 8000, 3 do not

    output = trajectory.read(1, 3)

    assert len(output) <= MAX_OUTPUT_CHARS
    assert output.count("Step ") == 2
    assert "[2 of 3 steps shown; remaining omitted, character budget]" in output
    assert "entry truncated" not in output  # whole entries dropped, none sliced


def test_every_read_and_search_result_respects_the_hard_output_bound():
    """Contract: every read/search result satisfies len(result) <= MAX_OUTPUT_CHARS,
    across a spread of adversarial entry sizes, never just the common case."""
    trajectory = Trajectory()
    for size in [1, 100, MAX_OUTPUT_CHARS - 1, MAX_OUTPUT_CHARS, MAX_OUTPUT_CHARS + 1, MAX_OUTPUT_CHARS * 5]:
        _append_step(trajectory, "z" * size, ["choice text"], 1, "choice text")

    for start in range(1, len(trajectory) + 1):
        assert len(trajectory.read(start, MAX_READ_COUNT)) <= MAX_OUTPUT_CHARS

    assert len(trajectory.search("choice", MAX_SEARCH_RESULTS)) <= MAX_OUTPUT_CHARS


def test_reset_removes_all_prior_episode_history():
    trajectory = Trajectory()
    _fill(trajectory, 4)
    assert len(trajectory) == 4

    trajectory.reset()

    assert len(trajectory) == 0
    assert trajectory.recent(10) == []
    assert trajectory.read(1, 1) == "error: no history recorded yet"
    assert trajectory.search("observation", 3) == "error: no history recorded yet"


def test_reset_restarts_step_numbering_from_one():
    trajectory = Trajectory()
    _fill(trajectory, 2)
    trajectory.reset()

    new_step = _append_step(trajectory, "Fresh episode start.", ["Go"], 1, "Go")

    assert new_step.step == 1


def test_never_mutates_earlier_entries_on_append():
    trajectory = Trajectory()
    first = _append_step(trajectory, "First.", ["A"], 1, "A")
    _append_step(trajectory, "Second.", ["B"], 1, "B")

    assert first.step == 1
    assert first.observation == "First."
    assert trajectory.recent(10)[0] == first
