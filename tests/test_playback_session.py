"""Machine à états de lecture (sans Qt) : reprise, boucle A-B, erreurs, états dérivés."""

from pathlib import Path

from hypothesis import given, strategies as st

from pyplayer.api.playback import AB_MIN_SPAN_MS, PlaybackSession, State
from pyplayer.api.video import Video


def video(name="a.mp4"):
    return Video(path=Path(name))


def test_initial_state_is_idle():
    assert PlaybackSession().state is State.IDLE


def test_load_without_resume_goes_ready():
    s = PlaybackSession()
    s.begin_load(video())
    assert s.state is State.LOADING
    assert s.on_loaded(60_000) is None and s.state is State.READY and s.resume_ready


def test_resume_seek_blocks_recording_until_reached():
    s = PlaybackSession()
    s.begin_load(video(), 30_000)
    assert s.on_loaded(60_000) == 30_000
    assert s.state is State.SEEKING_RESUME and not s.resume_ready
    s.on_position(100)                      # position « avant saut » : on reste en attente
    assert s.state is State.SEEKING_RESUME
    s.on_position(29_500)
    assert s.state is State.READY and s.resume_ready


def test_a_second_loaded_signal_never_leaves_seeking_and_ready_both_true():
    s = PlaybackSession()
    s.begin_load(video(), 1)
    assert s.on_loaded(1) is None and s.resume_ready          # durée trop courte : pas de reprise
    assert s.on_loaded(2) == 1                                 # signal en double, durée connue : reprise
    assert s.resume_seeking and not s.resume_ready and s.state is State.SEEKING_RESUME


def test_resume_target_beyond_duration_is_ignored():
    s = PlaybackSession()
    s.begin_load(video(), 90_000)
    assert s.on_loaded(60_000) is None and s.state is State.READY


def test_negative_resume_target_is_clamped():
    s = PlaybackSession()
    s.begin_load(video(), -5)
    assert s.resume_target == 0 and s.on_loaded(1000) is None


def test_unload_and_end_stop_recording():
    s = PlaybackSession()
    s.begin_load(video())
    s.on_loaded(1000)
    s.on_ended()
    assert not s.resume_ready and s.state is State.ENDED
    s.begin_load(video())
    s.on_loaded(1000)
    s.unload()
    assert not s.resume_ready and s.state is State.ENDED


def test_invalid_media_skips_at_most_one_lap():
    s = PlaybackSession()
    s.begin_load(video())
    decisions = [s.on_invalid(3) for _ in range(5)]
    assert decisions == [True, True, True, False, False] and s.state is State.ERROR
    s.on_loaded(1000)                       # un média valide remet le compteur à zéro
    assert s.error_streak == 0 and s.state is State.READY


def test_invalid_without_loaded_video_never_skips():
    assert PlaybackSession().on_invalid(5) is False


def test_ab_loop_cycle():
    s = PlaybackSession()
    assert s.cycle_ab(1000) == "a" and s.ab_a == 1000
    assert s.cycle_ab(1000 + AB_MIN_SPAN_MS) == "too_early" and s.ab_b is None
    assert s.cycle_ab(5000) == "b" and (s.ab_a, s.ab_b) == (1000, 5000)
    assert s.on_position(4999) is None
    assert s.on_position(5000) == 1000 and s.on_position(9000) == 1000
    assert s.cycle_ab(0) == "cleared" and (s.ab_a, s.ab_b) == (None, None)
    assert s.on_position(9000) is None


def test_new_load_clears_ab_loop():
    s = PlaybackSession()
    s.cycle_ab(0), s.cycle_ab(5000)
    s.begin_load(video())
    assert s.ab_a is None and s.ab_b is None
    assert s.clear_ab() is False


@given(st.lists(st.one_of(st.tuples(st.just("pos"), st.integers(0, 100_000)),
                          st.tuples(st.just("ab"), st.integers(0, 100_000)),
                          st.tuples(st.just("load"), st.integers(0, 100_000)),
                          st.tuples(st.just("done"), st.integers(0, 100_000)),
                          st.tuples(st.just("end"), st.just(0)),
                          st.tuples(st.just("bad"), st.just(0)),
                          st.tuples(st.just("unload"), st.just(0))), max_size=60))
def test_invariants_hold_under_any_event_sequence(events):
    s = PlaybackSession()
    for kind, value in events:
        if kind == "pos":
            s.on_position(value)
        elif kind == "ab":
            s.cycle_ab(value)
        elif kind == "load":
            s.begin_load(video(), value)
        elif kind == "done":
            s.on_loaded(value + 1)
        elif kind == "end":
            s.on_ended()
        elif kind == "bad":
            s.on_invalid(3)
        else:
            s.unload()
        assert not (s.resume_seeking and s.resume_ready)
        assert (s.ab_b is None) or (s.ab_a is not None and s.ab_b > s.ab_a)
        assert isinstance(s.state, State)
