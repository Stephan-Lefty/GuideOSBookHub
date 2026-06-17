from dataclasses import dataclass
from typing import Optional


@dataclass
class Bookmark:

    id: Optional[int]

    title: str

    url: str

    description: str = ""

    tags: str = ""

    group_id: Optional[int] = None

    favorite: bool = False


@dataclass
class Group:

    id: Optional[int]

    name: str

    parent_id: Optional[int] = None