"""Téléchargements sûrs de fichiers d'outils et de mises à jour (sans Qt, sans dépendance externe).

Règles : HTTPS uniquement, hôtes autorisés (à chaque redirection aussi), taille limitée, écriture dans un fichier
temporaire, **somme SHA-256 obligatoire** avant de rendre le fichier, remplacement atomique, annulation possible.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

USER_AGENT = "PyPlayer-updater"
TIMEOUT_S = 30
CHUNK = 256 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
GITHUB_HOSTS = frozenset({"api.github.com", "github.com", "objects.githubusercontent.com",
                          "release-assets.githubusercontent.com", "github-releases.githubusercontent.com"})


class FetchError(Exception):
    """Échec de téléchargement ou de vérification, avec un message lisible."""


@dataclass(frozen=True)
class FetchPolicy:
    allowed_hosts: frozenset[str] = GITHUB_HOSTS
    require_https: bool = True
    max_redirects: int = 5
    extra: dict[str, Any] = field(default_factory=dict, compare=False)

    def check(self, url: str) -> None:
        parsed = urlparse(url)
        if self.require_https and parsed.scheme.lower() != "https":
            raise FetchError("Adresse non sécurisée refusée (HTTPS obligatoire).")
        if parsed.scheme.lower() not in ("https", "http"):
            raise FetchError("Adresse refusée.")
        host = (parsed.hostname or "").lower()
        if host not in self.allowed_hosts:
            raise FetchError(f"Hôte non autorisé : {host or '?'}")


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    """Chaque redirection est revérifiée : un serveur autorisé ne peut pas nous envoyer ailleurs."""

    def __init__(self, policy: FetchPolicy) -> None:
        self.policy = policy
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802 -- surcharge urllib
        self.count += 1
        if self.count > self.policy.max_redirects:
            raise FetchError("Trop de redirections.")
        self.policy.check(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, policy: FetchPolicy, timeout: float):
    policy.check(url)
    opener = urllib.request.build_opener(_CheckedRedirects(policy))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        return opener.open(request, timeout=timeout)
    except FetchError:
        raise
    except urllib.error.HTTPError as error:
        raise FetchError(f"Le serveur a répondu {error.code}.") from error
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as error:
        raise FetchError(f"Connexion impossible : {getattr(error, 'reason', error)}") from error


def get_json(url: str, policy: FetchPolicy | None = None, timeout: float = TIMEOUT_S) -> Any:
    policy = policy or FetchPolicy()
    with _open(url, policy, timeout) as response:
        data = response.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise FetchError("Réponse trop volumineuse.")
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise FetchError("Réponse illisible.") from error


def get_text(url: str, policy: FetchPolicy | None = None, timeout: float = TIMEOUT_S, limit: int = 1_000_000) -> str:
    policy = policy or FetchPolicy()
    with _open(url, policy, timeout) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise FetchError("Fichier de sommes trop volumineux.")
    return data.decode("utf-8", errors="replace")


_SUM_LINE = re.compile(r"^([0-9a-fA-F]{64})\s+[ *]?(.+?)\s*$")


def parse_sums(text: str) -> dict[str, str]:
    """Fichier de sommes (``sha256sum`` ou ``SHA2-256SUMS``) -> {nom de fichier: somme en minuscules}."""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        match = _SUM_LINE.match(line.strip())
        if match:
            name = match.group(2).replace("\\", "/").rsplit("/", 1)[-1]
            sums[name] = match.group(1).lower()
    return sums


def sha256_of(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url: str, destination: Path | str, expected_sha256: str, *, policy: FetchPolicy | None = None,
                      max_bytes: int = 400 * 1024 * 1024, timeout: float = TIMEOUT_S,
                      progress: Callable[[int, int], None] | None = None,
                      cancelled: Callable[[], bool] | None = None) -> Path:
    """Télécharge ``url`` vers ``destination`` **seulement si** sa somme SHA-256 correspond. Rien n'est laissé en cas
    d'échec ; le fichier final est posé de façon atomique."""
    policy = policy or FetchPolicy()
    expected = (expected_sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise FetchError("Somme de contrôle absente ou invalide : téléchargement refusé.")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    digest = hashlib.sha256()
    done = 0
    try:
        with _open(url, policy, timeout) as response, open(partial, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            if total > max_bytes:
                raise FetchError("Fichier trop volumineux : téléchargement refusé.")
            while chunk := response.read(CHUNK):
                if cancelled is not None and cancelled():
                    raise FetchError("Téléchargement annulé.")
                done += len(chunk)
                if done > max_bytes:
                    raise FetchError("Fichier trop volumineux : téléchargement refusé.")
                digest.update(chunk)
                out.write(chunk)
                if progress is not None:
                    progress(done, total)
        if digest.hexdigest() != expected:
            raise FetchError("Somme de contrôle incorrecte : le fichier est corrompu ou a été modifié. "
                             "Il a été supprimé.")
        os.replace(partial, destination)
        return destination
    except (FetchError, OSError):
        partial.unlink(missing_ok=True)
        raise
    except Exception as error:  # noqa: BLE001 -- jamais de fichier partiel laissé derrière
        partial.unlink(missing_ok=True)
        raise FetchError(f"Téléchargement interrompu : {error}") from error
    finally:
        if partial.exists() and not destination.exists():
            partial.unlink(missing_ok=True)


def version_key(text: str) -> tuple[int, ...]:
    """« v0.3.1 » / « 2026.08.19 » -> (0, 3, 1) / (2026, 8, 19) pour comparer deux versions (suffixes ignorés)."""
    numbers = re.findall(r"\d+", (text or "").split("+", 1)[0].split("-", 1)[0])
    return tuple(int(n) for n in numbers[:6]) or (0,)


def is_newer(candidate: str, current: str) -> bool:
    a, b = version_key(candidate), version_key(current)
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))
