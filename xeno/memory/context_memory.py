import json
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any

from xeno.config import XenoConfig


class ContextMemory:
    """File-based context memory. Stores user info, preferences, project state in JSON."""

    def __init__(self, config: XenoConfig):
        self.filepath = config.memory_dir / "context.json"
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.filepath.exists():
            try:
                return json.loads(self.filepath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"user": {}, "projects": {}, "preferences": {}, "facts": [], "updated_at": None}
        return {"user": {}, "projects": {}, "preferences": {}, "facts": [], "updated_at": None}

    def _save(self):
        self._data["updated_at"] = datetime.now().isoformat()
        self.filepath.write_text(json.dumps(self._data, indent=2, default=str), encoding="utf-8")

    def store(self, key: str, value: Any, category: str = "facts") -> str:
        if category not in self._data:
            self._data[category] = {}
        if category == "facts":
            entry = {"key": key, "value": value, "timestamp": datetime.now().isoformat(), "id": hashlib.md5(f"{key}{value}".encode()).hexdigest()[:8]}
            existing = [f for f in self._data["facts"] if f.get("key") == key]
            if existing:
                existing[0].update(entry)
            else:
                self._data["facts"].append(entry)
        else:
            self._data[category][key] = {"value": value, "timestamp": datetime.now().isoformat()}
        self._save()
        return f"Stored '{key}' in {category}"

    def retrieve(self, key: str, category: str = "facts") -> str:
        if category == "facts":
            matches = [f for f in self._data.get("facts", []) if f.get("key") == key]
            if matches:
                return json.dumps(matches[0], indent=2)
            return f"No fact found with key '{key}'"
        item = self._data.get(category, {}).get(key)
        if item:
            return json.dumps(item, indent=2)
        return f"No item found with key '{key}' in {category}"

    def search(self, query: str) -> str:
        results = []
        query_lower = query.lower()
        for fact in self._data.get("facts", []):
            if query_lower in str(fact.get("key", "")).lower() or query_lower in str(fact.get("value", "")).lower():
                results.append(fact)
        for cat_name, cat_data in self._data.items():
            if cat_name in ("facts", "updated_at"):
                continue
            if isinstance(cat_data, dict):
                for k, v in cat_data.items():
                    if query_lower in k.lower() or query_lower in str(v).lower():
                        results.append({"category": cat_name, "key": k, "value": v})
        if results:
            return json.dumps(results[:10], indent=2, default=str)
        return f"No results found for '{query}'"

    def delete(self, key: str, category: str = "facts") -> str:
        if category == "facts":
            before = len(self._data.get("facts", []))
            self._data["facts"] = [f for f in self._data["facts"] if f.get("key") != key]
            after = len(self._data["facts"])
            if before > after:
                self._save()
                return f"Deleted fact '{key}'"
            return f"No fact found with key '{key}'"
        if key in self._data.get(category, {}):
            del self._data[category][key]
            self._save()
            return f"Deleted '{key}' from {category}"
        return f"No item found with key '{key}' in {category}"

    def update(self, key: str, value: Any, category: str = "facts") -> str:
        return self.store(key, value, category)

    def list_all(self) -> str:
        summary = {}
        for cat_name, cat_data in self._data.items():
            if cat_name == "updated_at":
                summary["updated_at"] = cat_data
            elif cat_name == "facts":
                summary["facts_count"] = len(cat_data)
            elif isinstance(cat_data, dict):
                summary[cat_name] = list(cat_data.keys())
        return json.dumps(summary, indent=2, default=str)

    def get_context_string(self) -> str:
        parts = []
        for cat_name, cat_data in self._data.items():
            if cat_name == "updated_at":
                continue
            if cat_name == "facts":
                if cat_data:
                    parts.append(f"Known facts: {json.dumps(cat_data[:20], default=str)}")
            elif isinstance(cat_data, dict) and cat_data:
                parts.append(f"{cat_name}: {json.dumps(cat_data, default=str)}")
        return "\n".join(parts) if parts else "No context stored yet."
