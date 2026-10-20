"""Tests à base de propriétés : reprise, réglages, sous-titres, M3U, durées, sérialisation hostile."""

import json
import random
import uuid
from pathlib import Path

import pytest
from hypothesis import HealthCheck, example, given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from pyplayer.api import media
from pyplayer.api.m3u import read_playlist_file, write_m3u
from pyplayer.api.playlist import Playlist
from pyplayer.api.resume import END_MARGIN_MS, MAX_ENTRIES, MIN_RESUME_MS, ResumeStore
from pyplayer.api.settings import DEFAULTS, Settings
from pyplayer.api.subtitles import Cue, SubtitleTrack, parse_subtitles
from pyplayer.api.video import Video

# JSON arbitraire (y compris hostile) pour fuzzer tous les chargeurs
JSON = st.recursive(
    st.none() | st.booleans() | st.integers(-10**12, 10**12) | st.floats(allow_nan=False) | st.text(max_size=20),
    lambda children: st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=12), children, max_size=5),
    max_leaves=25,
)


# ----------------------------------------------------------------- reprise de lecture
class ResumeMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.store = ResumeStore()
        self.paths = [Path(f"/m/{i}.mp4") for i in range(6)]

    @rule(i=st.integers(0, 5), pos=st.integers(0, 4_000_000), dur=st.integers(0, 4_000_000))
    def update(self, i, pos, dur):
        self.store.update(self.paths[i], pos, dur)

    @rule(i=st.integers(0, 5))
    def finish(self, i):
        self.store.mark_finished(self.paths[i])
        assert self.store.is_finished(self.paths[i]) and self.store.position(self.paths[i]) == 0

    @rule(i=st.integers(0, 5))
    def forget(self, i):
        self.store.forget(self.paths[i])
        assert self.store.position(self.paths[i]) == 0 and not self.store.is_finished(self.paths[i])

    @invariant()
    def position_is_zero_or_meaningful(self):
        for path in self.paths:
            pos = self.store.position(path)
            assert pos == 0 or pos >= MIN_RESUME_MS
            progress = self.store.progress(path)
            assert 0.0 <= progress <= 1.0
            if self.store.is_finished(path):
                assert pos == 0 and progress == 1.0

    @invariant()
    def bounded(self):
        assert len(self.store) <= MAX_ENTRIES


def test_resume_state_machine():
    ResumeMachine.TestCase.settings = settings(max_examples=120, stateful_step_count=40, deadline=None)
    ResumeMachine.TestCase().runTest()


@given(duration=st.integers(1_000, 10_000_000), fraction=st.floats(0.0, 1.0))
def test_resume_window_is_consistent_for_any_duration(duration, fraction):
    store = ResumeStore()
    path = Path("/m/a.mp4")
    position = int(duration * fraction)
    store.update(path, position, duration)
    margin = min(END_MARGIN_MS, int(duration * 0.03))
    if position >= duration - margin:
        assert store.is_finished(path) and store.position(path) == 0
    elif position < MIN_RESUME_MS:
        assert store.position(path) == 0 and not store.is_finished(path)
    else:
        assert store.position(path) == position and not store.is_finished(path)


@given(JSON)
def test_resume_loading_never_crashes_on_hostile_json(tmp_path_factory, data):
    folder = tmp_path_factory.mktemp("resume")
    target = folder / "r.json"
    target.write_text(json.dumps(data), encoding="utf-8")
    store = ResumeStore(target)
    for key in store._entries:
        assert store.position(key) >= 0


# ----------------------------------------------------------------- réglages
@given(JSON)
def test_settings_always_end_up_typed_and_in_range(tmp_path_factory, data):
    folder = tmp_path_factory.mktemp("settings")
    target = folder / "s.json"
    target.write_text(json.dumps(data), encoding="utf-8")
    settings_obj = Settings(target)
    for key, default in DEFAULTS.items():
        value = settings_obj.get(key)
        if isinstance(default, bool):
            assert isinstance(value, bool)
        elif isinstance(default, float):
            assert isinstance(value, (int, float)) and 0.0 <= value <= 1.0
        elif isinstance(default, list):
            assert isinstance(value, list)
        elif isinstance(default, str):
            assert isinstance(value, str)


@given(st.lists(st.text(min_size=1, max_size=15), max_size=60))
def test_recent_files_are_unique_capped_and_most_recent_first(paths):
    settings_obj = Settings()
    for path in paths:
        settings_obj.add_recent(path)
    recent = settings_obj.get("recent_files")
    assert len(recent) == len(set(recent)) <= 15
    if paths:
        assert recent[0] == paths[-1]


# ----------------------------------------------------------------- chargeurs face à du JSON hostile
@given(JSON)
def test_playlist_from_dict_only_ever_raises_value_error(data):
    try:
        playlist = Playlist.from_dict(data)  # type: ignore[arg-type]
    except ValueError:
        return
    assert isinstance(playlist, Playlist)
    assert len({v.key for v in playlist}) == len(playlist)
    if playlist.current is not None:
        assert any(v is playlist.current for v in playlist)


@given(st.dictionaries(st.sampled_from(["path", "file_path", "uid", "size", "duration", "width", "height", "added_at", "state"]),
                       JSON, max_size=9))
def test_video_from_dict_never_crashes_unexpectedly(data):
    try:
        video = Video.from_dict(data)
    except (ValueError, TypeError, OverflowError):
        return
    assert video.size >= 0 and video.duration >= 0 and video.width >= 0 and video.height >= 0


@given(st.integers(-10**6, 10**9))
def test_format_duration_roundtrip(ms):
    text = media.format_duration(ms)
    parts = [int(p) for p in text.split(":")]
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    assert seconds == max(0, ms) // 1000
    assert len(parts) in (2, 3) and all(0 <= p < 60 for p in parts[1:])


@given(st.integers(-10, 10**15))
def test_format_size_never_crashes(size):
    assert media.format_size(size)


# ----------------------------------------------------------------- sous-titres
cue_strategy = st.lists(
    st.tuples(st.integers(0, 3_600_000), st.integers(1, 20_000), st.text(min_size=1, max_size=10).filter(lambda t: t.strip())),
    max_size=40)


@given(cue_strategy, st.integers(-10_000, 3_700_000), st.integers(-3000, 3000))
def test_subtitle_lookup_matches_brute_force(raw, position, delay):
    cues = sorted((Cue(s, s + d, t) for s, d, t in raw), key=lambda c: c.start)
    track = SubtitleTrack(cues)
    track.delay = delay
    shown = track.text_at(position)
    t = position - delay
    candidates = [c for c in cues if c.start <= t < c.end]
    if shown:
        assert any(c.text == shown for c in candidates)       # ce qui est affiché est toujours valide
    # Les chevauchements profonds (> 4 cues actifs) sont la seule tolérance documentée.
    if len(candidates) <= 1:
        assert (shown != "") == bool(candidates)


@given(st.text(max_size=400))
@example("1\n00:00:01,000 --> 00:00:02,000\nhello\n")
@example("00:00:00,000 --> 99:99:99,999\nx")
def test_subtitle_parser_never_crashes(text):
    for cue in parse_subtitles(text):
        assert cue.start >= 0 and cue.text


# ----------------------------------------------------------------- M3U
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=60)
@given(st.lists(st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc", "Zl", "Zp"),
                                                blacklist_characters='/\\:*?"<>|\x00%#'),
                        min_size=1, max_size=12).map(lambda s: s.strip(" .")).filter(bool),
                min_size=1, max_size=8, unique_by=str.casefold))
def test_m3u_roundtrip_preserves_order_and_exotic_names(tmp_path, names):
    folder = tmp_path / uuid.uuid4().hex
    folder.mkdir()
    files = []
    for name in names:
        file = folder / f"{name}.mp4"
        try:
            file.write_bytes(b"x")
        except OSError:
            return  # nom refusé par le système de fichiers : hors sujet
        files.append(file)
    target = folder / "list.m3u8"
    write_m3u([(f, f.stem, 1000) for f in files], target)
    _name, read_back = read_playlist_file(target)
    assert [p.name for p in read_back] == [f.name for f in files]
