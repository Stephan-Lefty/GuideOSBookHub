from dataclasses import dataclass


@dataclass
class ProviderDefinition:
    id: str  # rclone-Backend-Typ (bzw. "local" als Sonderfall ohne Remote)
    label_key: str  # core/i18n.py-Schlüssel für den Anzeigenamen
    auth_kind: str  # "credentials" | "credentials_2fa" | "oauth" | "local"


PROVIDERS = [
    ProviderDefinition("webdav", "cloud.provider.webdav", "credentials"),
    ProviderDefinition("protondrive", "cloud.provider.protondrive", "credentials_2fa"),
    ProviderDefinition("drive", "cloud.provider.drive", "oauth"),
    ProviderDefinition("onedrive", "cloud.provider.onedrive", "oauth"),
    ProviderDefinition("dropbox", "cloud.provider.dropbox", "oauth"),
    ProviderDefinition("pcloud", "cloud.provider.pcloud", "oauth"),
    ProviderDefinition("local", "cloud.provider.local", "local"),
]


def get_provider(provider_id: str) -> ProviderDefinition:
    return next(p for p in PROVIDERS if p.id == provider_id)
