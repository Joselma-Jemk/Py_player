"""État de lecture explicite, sans dépendance à Qt : reprise, boucle A-B, série d'erreurs.

``PlaybackSession`` ne parle pas au lecteur : l'interface lui indique ce qui se passe (média chargé, position
atteinte, erreur) et il répond par une décision (« se placer à tel instant », « enregistrer », « sauter »).
Toutes les transitions sont ainsi testables sans fenêtre ni FFmpeg.
"""

from __future__ import annotations

import enum

from .video import Video

RESUME_TOLERANCE_MS = 1500   # écart accepté entre la position de reprise demandée et celle du lecteur
AB_MIN_SPAN_MS = 500         # B doit se situer au moins 0,5 s après A


class State(enum.Enum):
    IDLE = "idle"                    # aucun média chargé
    LOADING = "loading"              # média demandé, pas encore prêt
    SEEKING_RESUME = "seeking"       # saut vers la position de reprise en cours
    READY = "ready"                  # lecture/pause normales, position enregistrée
    ENDED = "ended"                  # fin de média, position non enregistrée
    ERROR = "error"                  # média invalide


class PlaybackSession:
    def __init__(self) -> None:
        self.loaded_video: Video | None = None
        self.resume_target = 0
        self.resume_ready = False        # tant que faux, on n'enregistre pas la position
        self.resume_seeking = False
        self.error_streak = 0
        self.ab_a: int | None = None
        self.ab_b: int | None = None
        self.rate = 1.0
        self.subtitles = None            # SubtitleTrack | None (évite un import circulaire inutile)
        self.failed = False
        self.pending = False             # vrai entre « begin_load » et « on_loaded »

    # ------------------------------------------------------------------ état dérivé
    @property
    def state(self) -> State:
        if self.failed:
            return State.ERROR
        if self.resume_seeking:
            return State.SEEKING_RESUME
        if self.resume_ready:
            return State.READY
        if self.loaded_video is None:
            return State.IDLE
        return State.LOADING if self.pending else State.ENDED

    # ------------------------------------------------------------------ transitions
    def begin_load(self, video: Video | None, resume_target: int = 0) -> None:
        self.loaded_video = video
        self.resume_target = max(0, resume_target)
        self.resume_ready = False
        self.resume_seeking = False
        self.failed = False
        self.pending = video is not None
        self.clear_ab()

    def unload(self) -> None:
        """Arrêt ou fermeture : plus rien à enregistrer tant qu'un nouveau média n'est pas prêt."""
        self.resume_ready = False
        self.resume_seeking = False
        self.pending = False

    def on_loaded(self, duration: int) -> int | None:
        """Média prêt. Retourne la position où sauter (reprise) ou ``None`` si on démarre au début."""
        self.error_streak = 0
        self.failed = False
        self.pending = False
        if self.loaded_video is not None and self.resume_target > 0 and duration > self.resume_target:
            self.resume_seeking = True
            return self.resume_target
        self.resume_ready = True
        return None

    def on_position(self, position: int) -> int | None:
        """Position du lecteur. Retourne un instant où revenir (boucle A-B) ou ``None``."""
        if self.ab_a is not None and self.ab_b is not None and position >= self.ab_b:
            return self.ab_a
        if self.resume_seeking and abs(position - self.resume_target) <= RESUME_TOLERANCE_MS:
            self.finish_resume_seek()
        return None

    def finish_resume_seek(self) -> None:
        self.resume_seeking = False
        self.resume_ready = self.loaded_video is not None

    def on_ended(self) -> None:
        self.resume_ready = False
        self.resume_seeking = False

    def on_invalid(self, playlist_size: int) -> bool:
        """Média invalide. Retourne vrai s'il faut passer au suivant (jamais plus d'un tour de playlist)."""
        self.failed = True
        self.resume_ready = False
        self.resume_seeking = False
        self.error_streak += 1
        return self.loaded_video is not None and self.error_streak <= playlist_size

    # ------------------------------------------------------------------ boucle A-B
    def cycle_ab(self, position: int) -> str:
        """Pose A, puis B, puis efface. Retourne ``"a"``, ``"b"``, ``"too_early"`` ou ``"cleared"``."""
        if self.ab_a is None:
            self.ab_a = position
            return "a"
        if self.ab_b is None:
            if position <= self.ab_a + AB_MIN_SPAN_MS:
                return "too_early"
            self.ab_b = position
            return "b"
        self.clear_ab()
        return "cleared"

    def clear_ab(self) -> bool:
        had = self.ab_a is not None
        self.ab_a = self.ab_b = None
        return had
