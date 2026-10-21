"""Miniatures de la barre de progression : une image du film à l'endroit survolé, dans une bulle.

Un second lecteur invisible (sans sortie audio) décode les images demandées ; les résultats sont gardés dans un cache
(une image par « tranche » de la durée) pour que repasser au même endroit soit instantané. Les demandes sont temporisées :
en balayant la barre, seule la dernière position est réellement décodée.
"""

from __future__ import annotations

import logging
from collections import OrderedDict

from PySide6 import QtCore, QtGui, QtMultimedia, QtWidgets

from pyplayer.ui import theme

logger = logging.getLogger(__name__)

THUMB_WIDTH = 176
MAX_BUCKETS = 120             # nombre de miniatures distinctes par média (précision = durée / 120, au moins 1 s)
CACHE_LIMIT = 240
DEBOUNCE_MS = 90              # pas de décodage tant que la souris bouge vite
FRAME_TIMEOUT_MS = 1800       # une image qui n'arrive jamais ne bloque pas les demandes suivantes


class ThumbnailCache:
    """Cache d'images par tranche de durée (LRU), sans Qt : la logique de découpage est testable seule."""

    def __init__(self, limit: int = CACHE_LIMIT) -> None:
        self.limit = limit
        self.duration_ms = 0
        self._items: OrderedDict[int, object] = OrderedDict()

    def reset(self, duration_ms: int) -> None:
        self.duration_ms = max(0, int(duration_ms))
        self._items.clear()

    @property
    def step_ms(self) -> int:
        """Durée couverte par une miniature : 1 s au minimum, sinon durée / MAX_BUCKETS."""
        return max(1000, -(-self.duration_ms // MAX_BUCKETS)) if self.duration_ms else 1000

    def bucket(self, position_ms: int) -> int:
        position = min(max(0, int(position_ms)), max(0, self.duration_ms - 1))
        return position // self.step_ms

    def position_of(self, bucket: int) -> int:
        """Position décodée pour une tranche : son centre, pour représenter la tranche entière."""
        middle = bucket * self.step_ms + self.step_ms // 2
        return min(middle, max(0, self.duration_ms - 1))

    def get(self, bucket: int):
        image = self._items.get(bucket)
        if image is not None:
            self._items.move_to_end(bucket)
        return image

    def put(self, bucket: int, image) -> None:
        self._items[bucket] = image
        self._items.move_to_end(bucket)
        while len(self._items) > self.limit:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)


class ThumbnailProvider(QtCore.QObject):
    """Décode, à la demande, l'image du film à une position donnée."""

    thumbnail_ready = QtCore.Signal(int, QtGui.QImage)     # (tranche, image)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.cache = ThumbnailCache()
        self._source = ""
        self._player: QtMultimedia.QMediaPlayer | None = None     # créé au premier besoin (jamais pour l'audio)
        self._sink: QtMultimedia.QVideoSink | None = None
        self._loaded = False
        self._wanted: int | None = None       # tranche demandée en dernier
        self._decoding: int | None = None     # tranche en cours de décodage
        self._debounce = QtCore.QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._decode_wanted)
        self._timeout = QtCore.QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(FRAME_TIMEOUT_MS)
        self._timeout.timeout.connect(self._on_timeout)

    # ------------------------------------------------------------------ état
    @property
    def has_source(self) -> bool:
        return bool(self._source)

    def set_source(self, path: str | None, duration_ms: int = 0) -> None:
        """Nouveau média (chemin local), ou ``None`` : on arrête tout et on libère le second lecteur."""
        self._debounce.stop()
        self._timeout.stop()
        self._wanted = self._decoding = None
        self.cache.reset(duration_ms)
        if not path or duration_ms <= 0:
            self._source = ""
            self._release_player()
            return
        if path != self._source:
            self._loaded = False
            if self._player is not None:
                self._player.setSource(QtCore.QUrl.fromLocalFile(path))
        self._source = path

    def request(self, position_ms: int) -> None:
        """Demande la miniature de cette position : réponse immédiate si elle est en cache, sinon décodage temporisé."""
        if not self._source:
            return
        bucket = self.cache.bucket(position_ms)
        self._wanted = bucket
        cached = self.cache.get(bucket)
        if cached is not None:
            self._debounce.stop()
            self.thumbnail_ready.emit(bucket, cached)
            return
        self._debounce.start()

    def cancel(self) -> None:
        self._debounce.stop()
        self._wanted = None

    def shutdown(self) -> None:
        self.set_source(None)

    # ------------------------------------------------------------------ décodage
    def _ensure_player(self) -> None:
        if self._player is not None:
            return
        self._player = QtMultimedia.QMediaPlayer(self)
        self._sink = QtMultimedia.QVideoSink(self)
        self._player.setVideoSink(self._sink)               # pas de sortie audio : ce lecteur reste muet
        self._sink.videoFrameChanged.connect(self._on_frame)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(lambda *_: self._on_timeout())
        self._player.setSource(QtCore.QUrl.fromLocalFile(self._source))

    def _release_player(self) -> None:
        if self._player is not None:
            self._player.setSource(QtCore.QUrl())           # jamais stop() : peut bloquer avec le backend FFmpeg
            self._player.deleteLater()
            self._sink.deleteLater()
            self._player = self._sink = None
        self._loaded = False

    def _decode_wanted(self) -> None:
        if self._wanted is None or not self._source or self._decoding is not None:
            return
        self._ensure_player()
        if not self._loaded:
            return                                            # _on_status relancera dès que le média est prêt
        self._decoding = self._wanted
        self._timeout.start()
        self._player.setPosition(self.cache.position_of(self._decoding))
        self._player.pause()                                  # en pause, l'image de la nouvelle position est livrée

    def _on_status(self, status) -> None:
        Status = QtMultimedia.QMediaPlayer.MediaStatus
        if status in (Status.LoadedMedia, Status.BufferedMedia) and not self._loaded:
            self._loaded = True
            self._decode_wanted()

    def _on_frame(self, frame: QtMultimedia.QVideoFrame) -> None:
        bucket = self._decoding
        if bucket is None or not frame.isValid():
            return
        target = self.cache.position_of(bucket)
        start = frame.startTime()
        # Les images en retard d'une recherche précédente sont ignorées ; on accepte l'image de la bonne tranche.
        if start >= 0 and abs(start // 1000 - target) > max(self.cache.step_ms, 1500):
            return
        self._finish(bucket, frame.toImage())

    def _on_timeout(self) -> None:
        bucket, self._decoding = self._decoding, None
        self._timeout.stop()
        if bucket is not None:
            logger.debug("Miniature %s non livrée à temps", bucket)
        self._next_if_needed(bucket)

    def _finish(self, bucket: int, image: QtGui.QImage) -> None:
        self._timeout.stop()
        self._decoding = None
        if not image.isNull():
            image = image.scaledToWidth(THUMB_WIDTH, QtCore.Qt.TransformationMode.SmoothTransformation)
            self.cache.put(bucket, image)
            self.thumbnail_ready.emit(bucket, image)
        self._next_if_needed(bucket)

    def _next_if_needed(self, done: int | None) -> None:
        if self._wanted is not None and self._wanted != done and self.cache.get(self._wanted) is None:
            self._debounce.start()


class ThumbnailBubble(QtWidgets.QFrame):
    """Bulle flottante au-dessus de la barre : miniature + heure. Transparente à la souris (ne vole jamais le survol)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, QtCore.Qt.WindowType.ToolTip | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(f"""
            QFrame {{ background-color: {theme.PRINCIPAL_COLOR}; border: 1px solid {theme.HOVER_COLOR};
                      border-radius: 8px; }}
            QLabel {{ background: transparent; border: none; color: {theme.PRINCIPAL_TEXT_COLOR}; }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 5)
        layout.setSpacing(4)
        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedWidth(THUMB_WIDTH)
        self.image_label.setVisible(False)
        self.time_label = QtWidgets.QLabel("00:00:00")
        self.time_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(self.image_label)
        layout.addWidget(self.time_label)
        self.setFixedWidth(THUMB_WIDTH + 12)

    def set_time(self, text: str) -> None:
        if self.time_label.text() != text:
            self.time_label.setText(text)

    def set_image(self, image: QtGui.QImage | None) -> None:
        if image is None or image.isNull():
            self.image_label.setVisible(False)
        else:
            self.image_label.setPixmap(QtGui.QPixmap.fromImage(image))
            self.image_label.setFixedHeight(image.height())
            self.image_label.setVisible(True)
        self.adjustSize()

    def show_above(self, anchor: QtWidgets.QWidget, x: int) -> None:
        """Place la bulle au-dessus de ``anchor`` à l'abscisse ``x`` (coordonnées du widget), sans sortir de l'écran."""
        self.adjustSize()
        point = anchor.mapToGlobal(QtCore.QPoint(x, 0))
        left = point.x() - self.width() // 2
        screen = anchor.screen().availableGeometry() if anchor.screen() else None
        if screen is not None:
            left = max(screen.left() + 4, min(left, screen.right() - self.width() - 4))
        self.move(left, point.y() - self.height() - 10)
        if not self.isVisible():
            self.show()
