"""
JSON file cache with expiration — shared across all modules.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class Cache:
    def __init__(self, cache_dir: str = "cache", expiration_days: int = 7):
        self.cache_dir = cache_dir
        self.expiration_days = expiration_days
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_file(self, key: str) -> str:
        safe_key = "".join(x for x in key if x.isalnum() or x in "._- ")
        return os.path.join(self.cache_dir, f"{safe_key}.json")

    def get(self, key: str) -> Optional[Any]:
        cache_file = self._get_cache_file(key)
        if not os.path.exists(cache_file):
            return None
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_time = datetime.fromisoformat(data["timestamp"])
            if datetime.now() - cached_time > timedelta(days=self.expiration_days):
                os.remove(cache_file)
                return None
            return data["value"]
        except Exception:
            if os.path.exists(cache_file):
                os.remove(cache_file)
            return None

    def set(self, key: str, value: Any):
        cache_file = self._get_cache_file(key)
        data = {"timestamp": datetime.now().isoformat(), "value": value}
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def clear_expired(self):
        if not os.path.exists(self.cache_dir):
            return
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(self.cache_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cached_time = datetime.fromisoformat(data["timestamp"])
                    if datetime.now() - cached_time > timedelta(days=self.expiration_days):
                        os.remove(file_path)
                except Exception:
                    pass

    def clear_all(self):
        if not os.path.exists(self.cache_dir):
            return
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".json"):
                os.remove(os.path.join(self.cache_dir, filename))
