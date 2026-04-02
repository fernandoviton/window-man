"""Layout persistence — save and load window layouts as YAML."""

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class WindowEntry:
    """A window's identity and geometry, with an optional group tag."""

    title: str
    path: Optional[str]
    x: int
    y: int
    width: int
    height: int
    group: Optional[str] = None


def _entry_to_dict(entry: WindowEntry) -> dict:
    d = {"title": entry.title, "x": entry.x, "y": entry.y,
         "width": entry.width, "height": entry.height}
    if entry.path is not None:
        d["path"] = entry.path
    if entry.group is not None:
        d["group"] = entry.group
    return d


def _dict_to_entry(d: dict) -> WindowEntry:
    return WindowEntry(
        title=d["title"], path=d.get("path"),
        x=d["x"], y=d["y"], width=d["width"], height=d["height"],
        group=d.get("group"),
    )


def load_layout(path: str) -> list[WindowEntry]:
    """Read a YAML layout file. Returns [] if file is missing or invalid."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        return []
    if not isinstance(data, list):
        return []
    return [_dict_to_entry(d) for d in data]


def save_layout(path: str, entries: list[WindowEntry], replace_all: bool = False) -> None:
    """Save entries to YAML.

    replace_all=False (default): replaces entries whose group matches any group
    in the new entries, keeping other groups intact.
    replace_all=True: replaces the entire file contents with the new entries.
    """
    existing = []
    if not replace_all and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, list):
                existing = data
        except yaml.YAMLError:
            pass

    if replace_all:
        kept = [_entry_to_dict(e) for e in entries]
    else:
        # Determine which groups are being replaced
        new_groups = {e.group for e in entries}
        # Keep existing entries whose group is NOT being replaced
        kept = [d for d in existing if d.get("group") not in new_groups]
        kept.extend(_entry_to_dict(e) for e in entries)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(kept, f, default_flow_style=False, allow_unicode=True)
