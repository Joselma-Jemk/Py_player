"""Test à états de Playlist : des milliers de séquences d'opérations aléatoires comparées à un modèle de référence."""

import random
from pathlib import Path

import pytest
from hypothesis import example, given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule

from pyplayer.api.media import natural_key, path_key
from pyplayer.api.playlist import PlayMode, Playlist, SORT_KEYS

POOL_SIZE = 14
NAMES = ["a.mp4", "B.mkv", "ep1.mp4", "ep2.mp4", "ep10.mp4", "ep 3.avi", "é.mp3", "z.webm", "10.mp4", "9.mp4",
         "x² 2.mp4", "Ⅻ.mp4", "ep001.mp4", "ep01.mp4"]


@pytest.fixture(scope="module")
def pool(tmp_path_factory) -> list[Path]:
    folder = tmp_path_factory.mktemp("pool")
    paths = []
    for i, name in enumerate(NAMES[:POOL_SIZE]):
        path = folder / name
        path.write_bytes(b"x" * (i + 1))
        paths.append(path)
    return paths


class PlaylistMachine(RuleBasedStateMachine):
    """Compare Playlist à un modèle trivial (liste de clés) après chaque opération."""

    pool: list[Path] = []

    def __init__(self):
        super().__init__()
        self.playlist = Playlist("machine")
        self.model: list[str] = []          # clés dans l'ordre attendu
        self.expected_current: str | None = None
        random.seed(0)

    # ------------------------------------------------------------- opérations d'édition
    @rule(index=st.integers(0, POOL_SIZE - 1))
    def add(self, index):
        path = self.pool[index]
        added = self.playlist.add(path)
        if path_key(path) in self.model:
            assert added is None
        else:
            assert added is not None
            self.model.append(path_key(path))

    @rule(indexes=st.lists(st.integers(0, POOL_SIZE - 1), max_size=8))
    def add_many(self, indexes):
        added = self.playlist.add_many(self.pool[i] for i in indexes)
        expected_new = []
        for i in indexes:
            key = path_key(self.pool[i])
            if key not in self.model and key not in expected_new:
                expected_new.append(key)
        assert [v.key for v in added] == expected_new
        self.model.extend(expected_new)

    @precondition(lambda self: self.model)
    @rule(data=st.data())
    def remove(self, data):
        index = data.draw(st.integers(0, len(self.model) - 1))
        key = self.model.pop(index)
        assert self.playlist.remove(index) is True
        if self.expected_current == key:
            self.expected_current = None

    @precondition(lambda self: self.model)
    @rule(data=st.data())
    def remove_many(self, data):
        indexes = data.draw(st.lists(st.integers(0, len(self.model) - 1), max_size=5))
        doomed = {self.model[i] for i in indexes}
        count = self.playlist.remove_many(indexes)
        assert count == len(doomed)
        self.model = [k for k in self.model if k not in doomed]
        if self.expected_current in doomed:
            self.expected_current = None

    @precondition(lambda self: len(self.model) >= 2)
    @rule(data=st.data())
    def move(self, data):
        n = len(self.model)
        src, dst = data.draw(st.integers(0, n - 1)), data.draw(st.integers(0, n - 1))
        assert self.playlist.move(src, dst)
        self.model.insert(dst, self.model.pop(src))

    @precondition(lambda self: len(self.model) >= 2)
    @rule(data=st.data())
    def swap(self, data):
        n = len(self.model)
        a, b = data.draw(st.integers(0, n - 1)), data.draw(st.integers(0, n - 1))
        assert self.playlist.swap(a, b)
        self.model[a], self.model[b] = self.model[b], self.model[a]

    @rule(by=st.sampled_from(sorted(SORT_KEYS)), reverse=st.booleans())
    def sort(self, by, reverse):
        self.playlist.sort(by, reverse=reverse)
        videos = {v.key: v for v in self.playlist}
        reference = sorted((videos[k] for k in self.model), key=SORT_KEYS[by], reverse=reverse)
        self.model = [v.key for v in reference]

    @precondition(lambda self: len(self.model) >= 2)
    @rule(seed=st.integers(0, 10_000))
    def reorder(self, seed):
        videos = list(self.playlist)
        random.Random(seed).shuffle(videos)
        assert self.playlist.reorder(videos)
        self.model = [v.key for v in videos]

    @rule()
    def clear(self):
        self.playlist.clear()
        self.model.clear()
        self.expected_current = None

    # ------------------------------------------------------------- lecture
    @rule(mode=st.sampled_from(list(PlayMode)))
    def set_mode(self, mode):
        before = self.playlist.current
        self.playlist.set_mode(mode)
        assert self.playlist.play_mode is mode
        assert self.playlist.current is before  # changer de mode ne change jamais la vidéo courante

    @precondition(lambda self: self.model)
    @rule(data=st.data())
    def jump(self, data):
        index = data.draw(st.integers(0, len(self.model) - 1))
        video = self.playlist.set_current(index)
        assert video is self.playlist[index]
        self.expected_current = self.model[index]

    @rule()
    def unselect(self):
        self.playlist.set_current(None)
        self.expected_current = None

    @precondition(lambda self: self.model)
    @rule(auto=st.booleans())
    def next(self, auto):
        mode, n = self.playlist.play_mode, len(self.model)
        current_key = self.expected_current
        index = self.model.index(current_key) if current_key in self.model else -1
        result = self.playlist.next(auto=auto)
        if current_key is None:
            assert result is not None and result is self.playlist.current
            self.expected_current = result.key
            return
        if mode is PlayMode.LOOP_ONE and auto:
            assert result is not None and result.key == current_key
        elif mode is PlayMode.SHUFFLE:
            assert result is not None and result.key in self.model
            if n > 1:
                assert result.key != current_key        # jamais deux fois de suite la même vidéo
            self.expected_current = result.key
        else:
            wraps = mode in (PlayMode.LOOP_ALL, PlayMode.LOOP_ONE)
            if index + 1 < n:
                assert result is not None and result.key == self.model[index + 1]
                self.expected_current = result.key
            elif wraps:
                assert result is not None and result.key == self.model[0]
                self.expected_current = result.key
            else:
                assert result is None               # fin de liste : rien ne bouge
                assert self.playlist.current.key == current_key

    @precondition(lambda self: self.model)
    @rule()
    def previous(self):
        mode, n = self.playlist.play_mode, len(self.model)
        current_key = self.expected_current
        index = self.model.index(current_key) if current_key in self.model else -1
        result = self.playlist.previous()
        if current_key is None:
            assert result is not None
            self.expected_current = result.key
            return
        if mode is PlayMode.SHUFFLE:
            if result is not None:
                assert result.key in self.model
                self.expected_current = result.key
            else:
                assert self.playlist.current.key == current_key
            return
        wraps = mode in (PlayMode.LOOP_ALL, PlayMode.LOOP_ONE)
        if index > 0:
            assert result is not None and result.key == self.model[index - 1]
            self.expected_current = result.key
        elif wraps:
            assert result is not None and result.key == self.model[-1]
            self.expected_current = result.key
        else:
            assert result is None and self.playlist.current.key == current_key

    @rule()
    def roundtrip(self):
        restored = Playlist.from_dict(self.playlist.to_dict())
        assert [v.key for v in restored] == self.model
        assert restored.play_mode is self.playlist.play_mode
        assert (restored.current.key if restored.current else None) == \
               (self.playlist.current.key if self.playlist.current else None)

    # ------------------------------------------------------------- invariants
    @invariant()
    def order_matches_model(self):
        assert [v.key for v in self.playlist] == self.model

    @invariant()
    def index_is_consistent(self):
        keys = [v.key for v in self.playlist]
        assert len(keys) == len(set(keys)) == len(self.playlist)
        assert set(self.playlist._by_key) == set(keys)
        for key, video in self.playlist._by_key.items():
            assert video.key == key

    @invariant()
    def current_is_valid(self):
        current = self.playlist.current
        if current is None:
            assert self.playlist.current_index == -1
        else:
            assert any(v is current for v in self.playlist)
            assert self.playlist[self.playlist.current_index] is current
        assert (current.key if current else None) == (self.expected_current if self.expected_current in self.model else None)

    @invariant()
    def internals_never_reference_removed_videos(self):
        alive = {id(v) for v in self.playlist}
        assert all(id(v) in alive for v in self.playlist._history)
        assert self.playlist._played <= alive


def test_playlist_state_machine(pool):
    PlaylistMachine.pool = pool
    PlaylistMachine.TestCase.settings = settings(max_examples=150, stateful_step_count=45, deadline=None)
    case = PlaylistMachine.TestCase()
    case.runTest()


# ----------------------------------------------------------------- propriétés pointuelles
# Alphabet volontairement hostile : chiffres de toutes les écritures, exposants, fractions, chiffres romains, emoji…
HOSTILE = st.text(alphabet=st.one_of(
    st.characters(categories=("Nd", "No", "Nl", "Lu", "Ll", "Lo", "Zs", "Po", "Sk")),
    st.sampled_from(list("0123456789²³¹½ⅫⅣ٣٤०१२_.- ")),
), max_size=24)


@example("²", "1²2")
@example("a1²2b", "a١٢٣b")
@example("٣", "3")
@given(HOSTILE, HOSTILE)
def test_natural_key_is_total_and_never_raises(a, b):
    ka, kb = natural_key(a), natural_key(b)
    assert (ka <= kb) or (kb <= ka)           # comparable (pas de TypeError str/int) et ordre total
    assert natural_key(a) == ka               # déterministe


@given(st.lists(HOSTILE, min_size=0, max_size=30))
def test_natural_sort_is_idempotent_and_stable_under_shuffle(names):
    once = sorted(names, key=natural_key)
    assert sorted(once, key=natural_key) == once
    shuffled = list(names)
    random.Random(1).shuffle(shuffled)
    assert [natural_key(x) for x in sorted(shuffled, key=natural_key)] == [natural_key(x) for x in once]


@given(st.lists(st.integers(1, 5000), min_size=2, max_size=12, unique=True))
def test_natural_sort_orders_numbers_numerically(numbers):
    names = [f"episode {n}.mp4" for n in numbers]
    assert sorted(names, key=natural_key) == [f"episode {n}.mp4" for n in sorted(numbers)]


@given(st.text(min_size=1, max_size=30).filter(lambda s: "\x00" not in s))
def test_path_key_is_idempotent(name):
    key = path_key(name)
    assert path_key(key) == key
