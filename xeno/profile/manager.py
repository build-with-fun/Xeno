"""Comprehensive User Profile — remembers EVERYTHING about the user."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class UserProfile:
    """Single JSON file storing everything about the user.

    Schema:
    {
      "identity": {"name", "nickname", "pronouns", "timezone"},
      "bio": {"birthday", "age", "location", "occupation", "company", "education"},
      "preferences": {"languages", "programming_languages", "tools", "themes",
                      "music", "food", "hobbies", "likes", "dislikes"},
      "relationships": [{"name", "relation", "notes"}],
      "possessions": [{"type", "name", "details"}],
      "goals": [{"goal", "status", "added_at"}],
      "schedule_events": [{"name", "date", "recurring"}],
      "skills": [],
      "history": [{"timestamp", "event", "category"}],
      "notes": [{"timestamp", "note"}],
      "metadata": {"created_at", "updated_at", "version"}
    }
    """

    DEFAULT = {
        "identity": {"name": "", "nickname": "", "pronouns": "", "timezone": ""},
        "bio": {"birthday": "", "age": 0, "location": "", "occupation": "", "company": "", "education": ""},
        "preferences": {
            "languages": [], "programming_languages": [], "tools": [],
            "themes": [], "music": [], "food": [], "hobbies": [],
            "likes": [], "dislikes": [],
        },
        "relationships": [],
        "possessions": [],
        "goals": [],
        "schedule_events": [],
        "skills": [],
        "history": [],
        "notes": [],
        "metadata": {"created_at": 0, "updated_at": 0, "version": "1.0"},
    }

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load_or_init()

    def _load_or_init(self) -> dict:
        if not self.path.exists():
            d = json.loads(json.dumps(self.DEFAULT))  # deep copy
            d["metadata"]["created_at"] = time.time()
            self._save(d)
            return d
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            # Merge with defaults to handle schema evolution
            for k in self.DEFAULT:
                if k not in d:
                    d[k] = json.loads(json.dumps(self.DEFAULT[k]))
                elif isinstance(self.DEFAULT[k], dict) and isinstance(d[k], dict):
                    for kk in self.DEFAULT[k]:
                        if kk not in d[k]:
                            d[k][kk] = self.DEFAULT[k][kk]
            return d
        except Exception as e:
            logger.warning(f"Profile corrupted, resetting: {e}")
            d = json.loads(json.dumps(self.DEFAULT))
            d["metadata"]["created_at"] = time.time()
            self._save(d)
            return d

    def _save(self, data: Optional[dict] = None) -> None:
        data = data or self._data
        data["metadata"]["updated_at"] = time.time()
        try:
            self.path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Profile save failed: {e}")

    def get(self, dotpath: str, default: Any = None) -> Any:
        """Get a value by dot-path: 'identity.name' or 'preferences.languages'."""
        val = self._data
        for k in dotpath.split("."):
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, dotpath: str, value: Any) -> None:
        keys = dotpath.split(".")
        val = self._data
        for k in keys[:-1]:
            if k not in val or not isinstance(val[k], dict):
                val[k] = {}
            val = val[k]
        val[keys[-1]] = value
        self._save()

    def append_to(self, dotpath: str, value: Any) -> None:
        current = self.get(dotpath, [])
        if not isinstance(current, list):
            current = []
        if isinstance(value, list):
            current.extend(value)
        else:
            if value not in current:
                current.append(value)
        self.set(dotpath, current)

    def add_history(self, event: str, category: str = "general") -> None:
        self.append_to("history", {
            "timestamp": time.time(),
            "event": event,
            "category": category,
        })

    def add_note(self, note: str) -> None:
        self.append_to("notes", {"timestamp": time.time(), "note": note})

    def add_goal(self, goal: str) -> None:
        goals = self.get("goals", [])
        goals.append({"goal": goal, "status": "active", "added_at": time.time()})
        self.set("goals", goals)

    def add_relationship(self, name: str, relation: str, notes: str = "") -> None:
        rels = self.get("relationships", [])
        for r in rels:
            if r.get("name", "").lower() == name.lower():
                r["relation"] = relation
                if notes:
                    r["notes"] = notes
                self._save()
                return
        rels.append({"name": name, "relation": relation, "notes": notes})
        self.set("relationships", rels)

    def add_schedule_event(self, name: str, date: str, recurring: str = "") -> None:
        events = self.get("schedule_events", [])
        events.append({"name": name, "date": date, "recurring": recurring})
        self.set("schedule_events", events)

    def update_from_fact(self, subject: str, predicate: str, obj: str, category: str) -> None:
        """Update profile based on a fact extracted by the brain."""
        if subject.startswith("user."):
            path = subject[5:]  # 'name', 'birthday', 'preferences.languages'
        elif subject == "user":
            path = self._category_to_path(category, predicate)
        else:
            path = subject

        # Map common subjects to profile paths
        path_map = {
            "name": "identity.name",
            "nickname": "identity.nickname",
            "pronouns": "identity.pronouns",
            "timezone": "identity.timezone",
            "birthday": "bio.birthday",
            "age": "bio.age",
            "location": "bio.location",
            "occupation": "bio.occupation",
            "job": "bio.occupation",
            "company": "bio.company",
            "education": "bio.education",
        }
        if path.lower() in path_map:
            path = path_map[path.lower()]

        list_fields = {
            "preferences.languages", "preferences.programming_languages",
            "preferences.tools", "preferences.themes", "preferences.music",
            "preferences.food", "preferences.hobbies", "preferences.likes",
            "preferences.dislikes", "skills",
        }
        if path in list_fields:
            self.append_to(path, obj)
            self.add_history(f"Added to {path}: {obj}", category)
            return

        if category == "relationship":
            self.add_relationship(obj, predicate)
            return

        if category == "goal":
            self.add_goal(obj)
            return

        if category == "schedule":
            self.add_schedule_event(predicate, obj, recurring="yearly" if "birthday" in subject else "")
            return

        try:
            old_val = self.get(path)
            self.set(path, obj)
            if old_val is not None and old_val != obj and old_val != "":
                self.add_history(f"Changed {path} from '{old_val}' to '{obj}'", category)
            else:
                self.add_history(f"Set {path} = {obj}", category)
        except Exception as e:
            logger.warning(f"Couldn't set profile path {path}: {e}")
            self.add_note(f"{subject} {predicate} {obj} ({category})")

    def _category_to_path(self, category: str, predicate: str) -> str:
        if category == "identity":
            return "identity.name"
        elif category == "bio":
            return f"bio.{predicate}"
        elif category == "preference":
            return "preferences.likes"
        elif category == "schedule":
            return "schedule_events"
        elif category == "skill":
            return "skills"
        elif category == "possession":
            return "possessions"
        elif category == "goal":
            return "goals"
        return "notes"

    def summary(self) -> str:
        """Brief summary for the brain to use as context."""
        lines = []
        name = self.get("identity.name", "")
        if name:
            lines.append(f"Name: {name}")
        birthday = self.get("bio.birthday", "")
        if birthday:
            lines.append(f"Birthday: {birthday}")
        location = self.get("bio.location", "")
        if location:
            lines.append(f"Location: {location}")
        occupation = self.get("bio.occupation", "")
        if occupation:
            lines.append(f"Occupation: {occupation}")
        company = self.get("bio.company", "")
        if company:
            lines.append(f"Company: {company}")

        all_prefs = {
            "Food": self.get("preferences.food", []),
            "Hobbies": self.get("preferences.hobbies", []),
            "Music": self.get("preferences.music", []),
            "Languages": self.get("preferences.languages", []),
            "Programming languages": self.get("preferences.programming_languages", []),
            "Tools": self.get("preferences.tools", []),
            "Themes": self.get("preferences.themes", []),
            "Likes": self.get("preferences.likes", []),
            "Dislikes": self.get("preferences.dislikes", []),
        }
        for label, items in all_prefs.items():
            if items:
                lines.append(f"Favorite {label.lower()}: {', '.join(items[:5])}")

        goals = self.get("goals", [])
        active = [g["goal"] for g in goals if g.get("status") == "active"]
        if active:
            lines.append(f"Active goals: {'; '.join(active[:3])}")
        rels = self.get("relationships", [])
        if rels:
            lines.append(f"Relationships: {', '.join(r['name'] + ' (' + r.get('relation', '?') + ')' for r in rels[:5])}")
        if not lines:
            return "(nothing known yet — this is a new user)"
        return "\n".join(lines)

    def full_profile(self) -> dict:
        return self._data

    def reset(self) -> None:
        self._data = json.loads(json.dumps(self.DEFAULT))
        self._data["metadata"]["created_at"] = time.time()
        self._save()

    def stats(self) -> dict:
        filled = sum(1 for k, v in self._data.items() if v and v != [])
        return {
            "fields_filled": filled,
            "history_entries": len(self.get("history", [])),
            "notes": len(self.get("notes", [])),
            "goals": len(self.get("goals", [])),
        }
