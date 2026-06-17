import json
from pathlib import Path


CONFIG_DIR = Path.home() / ".bookmarkhub"

CONFIG_DIR.mkdir(exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "settings.json"


class Settings:

    DEFAULT_SETTINGS = {
        "theme": "system",
        "sync_interval": 15,
        "auto_sync": True
    }

    @classmethod
    def load(cls):

        if not CONFIG_FILE.exists():

            cls.save(
                cls.DEFAULT_SETTINGS
            )

            return cls.DEFAULT_SETTINGS

        with open(CONFIG_FILE, "r") as f:

            return json.load(f)

    @classmethod
    def save(cls, settings):

        with open(CONFIG_FILE, "w") as f:

            json.dump(
                settings,
                f,
                indent=4
            )