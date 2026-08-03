import os
import shutil
import subprocess
from typing import Optional


def _rclone_binary() -> str:
    """Name/Pfad des zu verwendenden rclone-Binaries. In AppImage/Flatpak-
    Builds sorgt bereits das Startskript bzw. der Sandbox-PATH dafür, dass
    ein mitgeliefertes rclone gefunden wird (siehe packaging/); die
    Umgebungsvariable dient nur als expliziter Override für Sonderfälle."""
    return os.environ.get("GUIDEOSBOOKHUB_RCLONE", "rclone")


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
    full_args = [_rclone_binary(), "--retries", "1"] + args
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


INSTALL_SCRIPT_URL = "https://rclone.org/install.sh"


def is_rclone_installed() -> bool:
    return shutil.which(_rclone_binary()) is not None


def install_rclone(timeout: int = 300) -> None:
    """Installiert rclone systemweit über das offizielle Installationsskript.
    Nutzt pkexec für die Rechteausweitung statt sudo/gksudo/kdesudo, da
    PolicyKit auf praktisch jeder modernen Linux-Distribution und
    Desktop-Umgebung vorhanden ist (zeigt automatisch den passenden
    grafischen Passwort-Dialog von GNOME, KDE, XFCE, ...)."""

    command = ["pkexec", "bash", "-c", f"curl -fsSL {INSTALL_SCRIPT_URL} | bash"]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise RcloneError(
            "pkexec wurde nicht gefunden. Bitte rclone manuell installieren, "
            "z.B. mit 'sudo apt install rclone' oder über https://rclone.org/downloads/."
        )
    except subprocess.TimeoutExpired:
        raise RcloneTimeout(command)

    if result.returncode != 0:
        raise RcloneRemoteError(
            "Installation von rclone fehlgeschlagen oder abgebrochen.",
            stderr=(result.stderr or "").strip(),
        )


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


def _target(remote: str, path: str) -> str:
    """rclone behandelt einen bloßen Dateisystempfad ohne 'remote:'-Präfix
    bereits nativ als lokales Backend -- kein rclone-config-Eintrag nötig.
    Ein leerer remote-String steht daher für 'lokaler Ordner/USB-Stick'
    statt eines benannten Cloud-Remotes."""
    return f"{remote}:{path}" if remote else path


def check_remote_reachable(remote: str, path: str = "", timeout: int = 15) -> None:
    """Wirft RcloneRemoteError mit Klartext-Meldung, falls das Remote nicht
    erreichbar ist (Auth-Fehler, Netzwerkproblem, falscher Name, ...)."""

    target = _target(remote, path) if path else _target(remote, "")
    _run(["lsd", target], timeout=timeout)


def push_file(local_path: str, remote: str, remote_path: str, timeout: int = 60) -> None:
    _run(["copyto", local_path, _target(remote, remote_path)], timeout=timeout)


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

    target = _target(remote, directory) if directory else _target(remote, "")

    try:
        result = _run(["lsf", target, "--files-only"], timeout=timeout)
    except RcloneRemoteError:
        # Verzeichnis existiert noch nicht -> Datei existiert erst recht nicht.
        return False

    entries = {line.strip() for line in result.stdout.splitlines()}
    return filename in entries


def normalize_webdav_url(url: str, vendor: str, user: str) -> str:
    """Ergänzt bei Nextcloud/ownCloud automatisch den WebDAV-Pfad, falls der
    Nutzer nur die nackte Domain eingegeben hat (z.B. 'https://cloud.example.com'
    statt 'https://cloud.example.com/remote.php/dav/files/user/'). Ohne
    diesen Pfad antwortet der Server nur mit '405 Not Allowed', da auf der
    Domain selbst kein WebDAV läuft."""
    url = url.rstrip("/")
    if "/remote.php/" in url:
        return f"{url}/" if vendor in ("nextcloud", "owncloud") else url
    if vendor == "nextcloud":
        return f"{url}/remote.php/dav/files/{user}/"
    if vendor == "owncloud":
        return f"{url}/remote.php/webdav/"
    return url


def create_webdav_remote(name: str, url: str, vendor: str, user: str, password: str,
                          timeout: int = 30) -> None:
    """Legt ein WebDAV-Remote (Nextcloud/ownCloud/generisch) nicht-interaktiv
    an -- das GUI-Äquivalent zum manuellen `rclone config`-Dialog im
    Terminal. --obscure lässt rclone das Klartext-Passwort selbst vor dem
    Speichern in der Config-Datei verschlüsseln (identisch zum Verhalten
    des interaktiven Assistenten)."""
    _run(
        ["config", "create", name, "webdav",
         "url", url, "vendor", vendor, "user", user, "pass", password,
         "--obscure"],
        timeout=timeout,
    )


def create_protondrive_remote(name: str, email: str, password: str, twofa: str = "",
                               mailbox_password: str = "", timeout: int = 30) -> None:
    """Legt ein Proton-Drive-Remote nicht-interaktiv an. --obscure deckt
    sowohl 'pass' als auch 'mailbox-password' automatisch ab, da rclone
    beide Felder im protondrive-Backend als Passwort-Felder kennzeichnet."""
    args = ["config", "create", name, "protondrive", "username", email, "pass", password]
    if twofa:
        args += ["2fa", twofa]
    if mailbox_password:
        args += ["mailbox-password", mailbox_password]
    args.append("--obscure")
    _run(args, timeout=timeout)


def authorize_oauth(backend: str, timeout: int = 180) -> str:
    """Führt 'rclone authorize <backend>' aus -- öffnet den Standardbrowser
    für den OAuth-Login und liefert das dabei erzeugte Token als rohen
    JSON-String zurück, den create_oauth_remote() übernehmen kann."""
    result = _run(["authorize", backend], timeout=timeout)
    return _extract_oauth_token(result.stdout)


def _extract_oauth_token(output: str) -> str:
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return line
    raise RcloneRemoteError("Konnte OAuth-Token nicht aus rclone-Ausgabe extrahieren.")


def create_oauth_remote(name: str, backend: str, token_json: str, timeout: int = 30) -> None:
    _run(["config", "create", name, backend, "config_token", token_json], timeout=timeout)


def is_local_folder_writable(path: str) -> bool:
    """Für den USB-Stick/Lokaler-Ordner-Zweig: reine Dateisystemprüfung,
    kein rclone-Aufruf nötig, da es kein Remote-Konzept gibt."""
    return os.path.isdir(path) and os.access(path, os.W_OK)


def delete_remote(name: str, timeout: int = 15) -> None:
    _run(["config", "delete", name], timeout=timeout)


def pull_file(remote: str, remote_path: str, timeout: int = 60) -> Optional[str]:
    """Gibt den Dateiinhalt zurück, oder None, wenn die Datei auf dem Remote
    noch nicht existiert (z.B. beim allerersten Sync)."""

    if not _remote_file_exists(remote, remote_path, timeout):
        return None

    result = _run(["cat", _target(remote, remote_path)], timeout=timeout)
    return result.stdout
