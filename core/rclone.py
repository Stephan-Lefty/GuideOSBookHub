import shutil
import subprocess
from typing import Optional


class RcloneError(Exception):
    """Basisklasse für alle rclone-bezogenen Fehler."""


class RcloneNotInstalled(RcloneError):
    def __init__(self):
        super().__init__(
            "rclone wurde nicht gefunden. Bitte installieren, z.B. mit "
            "'sudo apt install rclone' oder dem Installer von https://rclone.org/downloads/."
        )


class RcloneTimeout(RcloneError):
    def __init__(self, args: list[str]):
        super().__init__(f"rclone hat nicht rechtzeitig geantwortet: {' '.join(args)}")


class RcloneRemoteError(RcloneError):
    """Nicht-Null-Exitcode von rclone. .stderr enthält rclones Originalmeldung,
    die unverändert in der GUI angezeigt wird (bewusst keine
    Provider-spezifische Fehlerklassifizierung)."""

    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.stderr = stderr


def _run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    full_args = ["rclone", "--retries", "1"] + args
    try:
        result = subprocess.run(
            full_args, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        raise RcloneNotInstalled()
    except subprocess.TimeoutExpired:
        raise RcloneTimeout(full_args)

    if result.returncode != 0:
        raise RcloneRemoteError(
            f"rclone-Befehl fehlgeschlagen: {' '.join(args)}", stderr=result.stderr.strip()
        )

    return result


def is_rclone_installed() -> bool:
    return shutil.which("rclone") is not None


def get_rclone_version() -> Optional[str]:
    if not is_rclone_installed():
        return None
    try:
        result = _run(["version"], timeout=15)
    except RcloneError:
        return None
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    return first_line.replace("rclone ", "").strip() or None


def list_remotes() -> list[str]:
    """Namen der konfigurierten rclone-Remotes, ohne abschließenden ':'.
    Leere Liste, falls noch keine Remotes eingerichtet sind (kein Fehler)."""

    if not is_rclone_installed():
        raise RcloneNotInstalled()

    result = _run(["listremotes"], timeout=15)
    return [line.strip().rstrip(":") for line in result.stdout.splitlines() if line.strip()]


def check_remote_reachable(remote: str, path: str = "", timeout: int = 15) -> None:
    """Wirft RcloneRemoteError mit Klartext-Meldung, falls das Remote nicht
    erreichbar ist (Auth-Fehler, Netzwerkproblem, falscher Name, ...)."""

    target = f"{remote}:{path}" if path else f"{remote}:"
    _run(["lsd", target], timeout=timeout)


def push_file(local_path: str, remote: str, remote_path: str, timeout: int = 60) -> None:
    _run(["copyto", local_path, f"{remote}:{remote_path}"], timeout=timeout)


def _remote_file_exists(remote: str, remote_path: str, timeout: int) -> bool:
    """Prüft per Verzeichnislisting, ob remote_path existiert. lsf direkt auf
    einen Dateipfad anzuwenden ist über Backends hinweg nicht zuverlässig
    (manche Backends interpretieren ihn als Verzeichnis-Präfix), daher wird
    stattdessen das enthaltende Verzeichnis gelistet und der Dateiname darin
    gesucht."""

    if "/" in remote_path:
        directory, filename = remote_path.rsplit("/", 1)
    else:
        directory, filename = "", remote_path

    target = f"{remote}:{directory}" if directory else f"{remote}:"

    try:
        result = _run(["lsf", target, "--files-only"], timeout=timeout)
    except RcloneRemoteError:
        # Verzeichnis existiert noch nicht -> Datei existiert erst recht nicht.
        return False

    entries = {line.strip() for line in result.stdout.splitlines()}
    return filename in entries


def pull_file(remote: str, remote_path: str, timeout: int = 60) -> Optional[str]:
    """Gibt den Dateiinhalt zurück, oder None, wenn die Datei auf dem Remote
    noch nicht existiert (z.B. beim allerersten Sync)."""

    if not _remote_file_exists(remote, remote_path, timeout):
        return None

    result = _run(["cat", f"{remote}:{remote_path}"], timeout=timeout)
    return result.stdout
