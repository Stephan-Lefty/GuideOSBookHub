from dataclasses import dataclass, field
from typing import Optional
import uuid


def new_uid() -> str:
    return str(uuid.uuid4())


@dataclass
class Bookmark:

    id: Optional[int]

    title: str

    url: str

    description: str = ""

    tags: str = ""

    group_id: Optional[int] = None

    favorite: bool = False

    uid: str = field(default_factory=new_uid)

    modified: Optional[str] = None


@dataclass
class Group:

    id: Optional[int]

    name: str

    parent_id: Optional[int] = None

    # Nur bei Top-Level-Gruppen (parent_id is None) gesetzt; verschachtelte
    # Gruppen erben das Profil ihrer obersten Vorfahren-Gruppe zur Laufzeit.
    profile_id: Optional[str] = None

    uid: str = field(default_factory=new_uid)

    modified: Optional[str] = None
