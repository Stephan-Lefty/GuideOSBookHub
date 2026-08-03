import json
import uuid
from pathlib import Path


CONFIG_DIR = Path.home() / ".guideosbookhub"

CONFIG_DIR.mkdir(exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "settings.json"


class Settings:

    DEFAULT_SETTINGS = {
        "theme": "system",
        "language": "de",
        "profiles": [],
        "onboarding_shown": False,
    }

    @classmethod
    def load(cls):

        if not CONFIG_FILE.exists():

            cls.save(
                cls.DEFAULT_SETTINGS
            )

            return dict(cls.DEFAULT_SETTINGS)

        with open(CONFIG_FILE, "r") as f:

            settings = json.load(f)

        settings.setdefault("theme", cls.DEFAULT_SETTINGS["theme"])
        settings.setdefault("language", cls.DEFAULT_SETTINGS["language"])
        settings.setdefault("profiles", [])
        settings.setdefault("onboarding_shown", False)

        return settings

    @classmethod
    def save(cls, settings):

        with open(CONFIG_FILE, "w") as f:

            json.dump(
                settings,
                f,
                indent=4
            )

    # ---------- Sync-Profile ----------
    # Jedes Profil verbindet einen konfigurierten rclone-Remote (siehe
    # core/rclone.py) mit einem Dateipfad auf diesem Remote. Mehrere
    # Profile können gleichzeitig existieren (z.B. "Arbeit" -> Nextcloud,
    # "Privat" -> Proton Drive).

    @classmethod
    def list_profiles(cls) -> list[dict]:
        return cls.load()["profiles"]

    @classmethod
    def get_profile(cls, profile_id: str) -> dict | None:
        for profile in cls.list_profiles():
            if profile["id"] == profile_id:
                return profile
        return None

    @classmethod
    def add_profile(cls, name: str, remote: str, remote_path: str,
                     sync_interval: int = 15, auto_sync: bool = True) -> dict:
        settings = cls.load()
        profile = {
            "id": str(uuid.uuid4()),
            "name": name,
            "remote": remote,
            "remote_path": remote_path,
            "sync_interval": sync_interval,
            "auto_sync": auto_sync,
        }
        settings["profiles"].append(profile)
        cls.save(settings)
        return profile

    @classmethod
    def update_profile(cls, profile_id: str, **fields) -> None:
        settings = cls.load()
        for profile in settings["profiles"]:
            if profile["id"] == profile_id:
                profile.update(fields)
                break
        cls.save(settings)

    @classmethod
    def remove_profile(cls, profile_id: str) -> None:
        settings = cls.load()
        settings["profiles"] = [p for p in settings["profiles"] if p["id"] != profile_id]
        cls.save(settings)

    # ---------- Onboarding ----------

    @classmethod
    def is_onboarding_shown(cls) -> bool:
        return cls.load()["onboarding_shown"]

    @classmethod
    def mark_onboarding_shown(cls) -> None:
        settings = cls.load()
        settings["onboarding_shown"] = True
        cls.save(settings)

    # ---------- Sprache ----------

    @classmethod
    def get_language(cls) -> str:
        return cls.load()["language"]

    @classmethod
    def set_language(cls, language: str) -> None:
        settings = cls.load()
        settings["language"] = language
        cls.save(settings)
