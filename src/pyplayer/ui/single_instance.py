"""Instance unique : « Ouvrir avec… » envoie les fichiers à la fenêtre déjà ouverte au lieu d'en lancer une autre."""

from __future__ import annotations

import functools
import getpass
import json
import re

from PySide6 import QtCore, QtNetwork

from pyplayer import APP_NAME


def _server_name() -> str:
    user = re.sub(r"[^\w.-]", "_", getpass.getuser() or "user")
    return f"{APP_NAME.lower()}-{user}"


class SingleInstance(QtCore.QObject):
    """Serveur local qui reçoit ``{"paths": [...], "enqueue": bool}`` d'une seconde instance.

    Cycle de vie des sockets (point délicat de PySide) : chaque connexion entrante appartient au serveur, accumule
    ses octets et est traitée **une seule fois**, à la déconnexion ; elle n'est supprimée qu'à cet endroit.
    """

    message_received = QtCore.Signal(list, bool)

    def __init__(self, parent=None, name: str | None = None) -> None:
        super().__init__(parent)
        self._name = name or _server_name()
        self._server: QtNetwork.QLocalServer | None = None
        self._buffers: dict[int, bytearray] = {}   # id(socket) -> octets reçus

    # ------------------------------------------------------------------ client
    def send_to_running(self, paths: list[str], enqueue: bool = False, timeout_ms: int = 800) -> bool:
        """Transmet les chemins à l'instance en cours. Retourne False s'il n'y en a pas."""
        socket = QtNetwork.QLocalSocket()
        try:
            socket.connectToServer(self._name)
            if not socket.waitForConnected(timeout_ms):
                return False
            socket.write(json.dumps({"paths": paths, "enqueue": enqueue}).encode("utf-8"))
            socket.flush()
            socket.waitForBytesWritten(timeout_ms)
            socket.disconnectFromServer()
            if socket.state() != QtNetwork.QLocalSocket.LocalSocketState.UnconnectedState:
                socket.waitForDisconnected(timeout_ms)
            return True
        finally:
            socket.abort()   # l'objet est détenu par Python : aucun deleteLater, il est libéré proprement à la sortie

    # ------------------------------------------------------------------ serveur
    def listen(self) -> bool:
        QtNetwork.QLocalServer.removeServer(self._name)  # supprime un socket orphelin (crash précédent)
        self._server = QtNetwork.QLocalServer(self)
        self._server.setSocketOptions(QtNetwork.QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._on_connection)
        return self._server.listen(self._name)

    def close(self) -> None:
        """Arrête d'écouter et libère les connexions en cours."""
        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None
        self._buffers.clear()

    def _on_connection(self) -> None:
        while self._server is not None and self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                break
            self._buffers[id(socket)] = bytearray()
            socket.readyRead.connect(functools.partial(self._on_ready_read, socket))
            socket.disconnected.connect(functools.partial(self._on_disconnected, socket))
            if socket.bytesAvailable():
                self._on_ready_read(socket)

    def _on_ready_read(self, socket: QtNetwork.QLocalSocket) -> None:
        buffer = self._buffers.get(id(socket))
        if buffer is not None:
            buffer += bytes(socket.readAll().data())

    def _on_disconnected(self, socket: QtNetwork.QLocalSocket) -> None:
        buffer = self._buffers.pop(id(socket), bytearray())
        buffer += bytes(socket.readAll().data())
        socket.deleteLater()                                   # unique point de suppression
        try:
            data = json.loads(bytes(buffer).decode("utf-8"))
            paths = [str(p) for p in data.get("paths", [])]
            enqueue = bool(data.get("enqueue", False))
        except (ValueError, AttributeError, UnicodeDecodeError):
            return
        self.message_received.emit(paths, enqueue)
