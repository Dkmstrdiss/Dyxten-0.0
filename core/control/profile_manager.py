import copy
import json
from pathlib import Path
from typing import Dict, Iterable, Optional

try:
    from .config import DEFAULTS, PROFILE_PRESETS
except ImportError:  # pragma: no cover
    from core.control.config import DEFAULTS, PROFILE_PRESETS


class ProfileManager:
    """Persist and retrieve parameter profiles."""

    DEFAULT_PROFILE = "Default"

    def __init__(self, storage_path: Optional[Path] = None):
        base_dir = Path.home() / ".dyxten"
        self.path = storage_path or (base_dir / "profiles.json")
        self._profiles: Dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------ utils
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._profiles = {
                    str(name): self._sanitize_profile(data)
                    for name, data in raw.items()
                    if isinstance(data, dict)
                }
            else:
                self._profiles = {}
        except FileNotFoundError:
            self._profiles = {}
        except Exception:
            self._profiles = {}

        changed = self.ensure_default(DEFAULTS)
        if self.ensure_presets(PROFILE_PRESETS):
            changed = True
        if changed:
            self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialisable = {name: data for name, data in sorted(self._profiles.items())}
        self.path.write_text(
            json.dumps(serialisable, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _sanitize_profile(data: Optional[dict]) -> dict:
        if not isinstance(data, dict):
            return {}
        sanitized: Dict[str, dict] = {}
        for section, values in data.items():
            if isinstance(values, dict):
                sanitized[str(section)] = copy.deepcopy(values)
        return sanitized

    @staticmethod
    def _merge(base: dict, override: dict) -> dict:
        out = copy.deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key].update(copy.deepcopy(value))
            else:
                out[key] = copy.deepcopy(value)
        return out

    @staticmethod
    def _coerce_state(state: dict) -> dict:
        coerced: Dict[str, dict] = {}
        for key, section in state.items():
            if isinstance(section, dict):
                coerced[key] = copy.deepcopy(section)
        return coerced

    # ---------------------------------------------------------------- profiles
    def ensure_default(self, defaults: dict) -> bool:
        if self.DEFAULT_PROFILE not in self._profiles:
            self._profiles[self.DEFAULT_PROFILE] = copy.deepcopy(defaults)
            return True
        return False

    def ensure_presets(self, presets: Dict[str, dict]) -> bool:
        changed = False
        for name, data in presets.items():
            if name not in self._profiles:
                self._profiles[name] = self._coerce_state(data)
                changed = True
        return changed

    def list_profiles(self) -> Iterable[str]:
        names = [n for n in self._profiles.keys() if n != self.DEFAULT_PROFILE]
        names.sort(key=str.lower)
        if self.DEFAULT_PROFILE in self._profiles:
            return [self.DEFAULT_PROFILE, *names]
        return names

    def has_profile(self, name: str) -> bool:
        return name in self._profiles

    def get_profile(self, name: str) -> dict:
        data = self._profiles.get(name)
        if data is None:
            data = self._profiles[self.DEFAULT_PROFILE]
        return self._merge(DEFAULTS, data)

    def save_profile(self, name: str, state: dict) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Profile name cannot be empty")
        self._profiles[clean_name] = self._coerce_state(state)
        self._write()

    def delete_profile(self, name: str) -> None:
        if name == self.DEFAULT_PROFILE:
            raise ValueError("Default profile cannot be deleted")
        if name in self._profiles:
            del self._profiles[name]
            self._write()

    def rename_profile(self, old: str, new: str) -> None:
        new_name = new.strip()
        if not new_name:
            raise ValueError("Profile name cannot be empty")
        if old == self.DEFAULT_PROFILE:
            raise ValueError("Default profile cannot be renamed")
        if old not in self._profiles:
            raise KeyError(old)
        if new_name in self._profiles:
            raise ValueError("Profile already exists")
        self._profiles[new_name] = self._profiles.pop(old)
        self._write()

    def profile_equals(self, name: str, state: dict) -> bool:
        if name not in self._profiles:
            return False
        return self._profiles[name] == self._coerce_state(state)

    def reload(self) -> None:
        self._load()
