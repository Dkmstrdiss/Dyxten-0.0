import copy
import json
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, List

try:
    from .config import DEFAULTS, PROFILE_PRESETS, SUBPROFILE_PRESETS
except ImportError:  # pragma: no cover
    from core.control.config import DEFAULTS, PROFILE_PRESETS, SUBPROFILE_PRESETS


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


class SubProfileManager:
    """Persist and retrieve per-section sub profiles."""

    DEFAULT_NAME = "Standard"
    CATEGORY_DEFAULT = "Défaut"
    CATEGORY_CUSTOM = "Personnalisés"
    CATEGORY_FALLBACK = "Préconfigurations"

    def __init__(self, storage_path: Optional[Path] = None):
        base_dir = Path.home() / ".dyxten"
        self.path = storage_path or (base_dir / "subprofiles.json")
        self._sections: Dict[str, Dict[str, dict]] = {}
        self._categories: Dict[str, Dict[str, str]] = {}
        self._load()

    # ------------------------------------------------------------------ utils
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                clean: Dict[str, Dict[str, dict]] = {}
                for section, payload in raw.items():
                    if not isinstance(payload, dict):
                        continue
                    clean_section: Dict[str, dict] = {}
                    for name, data in payload.items():
                        if isinstance(data, dict):
                            clean_section[str(name)] = self._sanitize_profile(data)
                    if clean_section:
                        clean[str(section)] = clean_section
                self._sections = clean
            else:
                self._sections = {}
        except FileNotFoundError:
            self._sections = {}
        except Exception:
            self._sections = {}

        self._categories = {}
        for section, store in self._sections.items():
            cat_map = self._categories.setdefault(section, {})
            for name in store.keys():
                cat_map.setdefault(name, self.CATEGORY_CUSTOM)

        if self._write_defaults():
            self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serialisable = {
            section: {name: data for name, data in sorted(store.items())}
            for section, store in sorted(self._sections.items())
        }
        self.path.write_text(
            json.dumps(serialisable, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _record_category(self, section: str, name: str, category: str) -> None:
        self._categories.setdefault(section, {})[name] = category

    @staticmethod
    def _iter_groups(spec) -> Iterable[Tuple[str, Dict[str, dict]]]:
        if isinstance(spec, dict):
            yield SubProfileManager.CATEGORY_FALLBACK, spec
            return
        if isinstance(spec, (list, tuple)):
            for entry in spec:
                if isinstance(entry, dict):
                    category = str(entry.get("category", SubProfileManager.CATEGORY_FALLBACK))
                    payload = entry.get("items")
                    if not isinstance(payload, dict):
                        payload = entry.get("presets")
                    if isinstance(payload, dict):
                        yield category, payload
                elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                    category = str(entry[0]) if isinstance(entry[0], str) else SubProfileManager.CATEGORY_FALLBACK
                    payload = entry[1] if isinstance(entry[1], dict) else None
                    if isinstance(payload, dict):
                        yield category, payload

    def _write_defaults(self) -> bool:
        changed = False
        for section, defaults in DEFAULTS.items():
            if not isinstance(defaults, dict):
                continue
            store = self._sections.setdefault(section, {})
            if self.DEFAULT_NAME not in store:
                store[self.DEFAULT_NAME] = self._sanitize_profile(defaults)
                changed = True
            self._record_category(section, self.DEFAULT_NAME, self.CATEGORY_DEFAULT)
        for section, presets in SUBPROFILE_PRESETS.items():
            store = self._sections.setdefault(section, {})
            if isinstance(presets, dict):
                for name, payload in presets.items():
                    if name not in store:
                        store[name] = self._sanitize_profile(payload)
                        changed = True
                    self._record_category(section, name, self.CATEGORY_FALLBACK)
                continue
            for category, group in self._iter_groups(presets):
                if not isinstance(group, dict):
                    continue
                label = category or self.CATEGORY_FALLBACK
                for name, payload in group.items():
                    if name not in store:
                        store[name] = self._sanitize_profile(payload)
                        changed = True
                    self._record_category(section, name, label)
        return changed

    @staticmethod
    def _sanitize_profile(data: Optional[dict]) -> dict:
        if not isinstance(data, dict):
            return {}
        return copy.deepcopy(data)

    # ---------------------------------------------------------------- storage
    def list(self, section: str) -> Iterable[str]:
        ordered: List[str] = []
        for _category, names in self.list_grouped(section):
            ordered.extend(names)
        return ordered

    def list_grouped(self, section: str) -> List[Tuple[str, List[str]]]:
        store = self._sections.get(section, {})
        if not store:
            return []
        cat_map = self._categories.get(section, {})
        groups: Dict[str, List[str]] = {}
        for name in store.keys():
            category = cat_map.get(name, self.CATEGORY_CUSTOM)
            groups.setdefault(category, []).append(name)

        def sort_names(names: List[str]) -> List[str]:
            return sorted(
                names,
                key=lambda n: (0 if n == self.DEFAULT_NAME else 1, n.lower()),
            )

        def category_key(cat: str) -> Tuple[int, str]:
            if cat == self.CATEGORY_DEFAULT:
                return (0, cat.lower())
            if cat == self.CATEGORY_CUSTOM:
                return (99, cat.lower())
            return (1, cat.lower())

        ordered = []
        for cat in sorted(groups.keys(), key=category_key):
            ordered.append((cat, sort_names(groups[cat])))
        return ordered

    def ensure_section(self, section: str, defaults: Optional[dict] = None) -> None:
        store = self._sections.setdefault(section, {})
        if self.DEFAULT_NAME not in store:
            store[self.DEFAULT_NAME] = self._sanitize_profile(defaults or {})
            self._write()
        self._record_category(section, self.DEFAULT_NAME, self.CATEGORY_DEFAULT)

    def get(self, section: str, name: str) -> dict:
        store = self._sections.get(section, {})
        data = store.get(name)
        if data is None:
            data = store.get(self.DEFAULT_NAME, {})
        return self._sanitize_profile(data)

    def save(self, section: str, name: str, payload: dict) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Sub-profile name cannot be empty")
        store = self._sections.setdefault(section, {})
        store[clean_name] = self._sanitize_profile(payload)
        self._record_category(section, clean_name, self.CATEGORY_CUSTOM)
        self._write()

    def delete(self, section: str, name: str) -> None:
        if name == self.DEFAULT_NAME:
            raise ValueError("Default sub-profile cannot be deleted")
        store = self._sections.get(section, {})
        if name in store:
            del store[name]
            cat_map = self._categories.get(section)
            if cat_map and name in cat_map:
                del cat_map[name]
            self._write()

    def rename(self, section: str, old: str, new: str) -> None:
        new_name = new.strip()
        if not new_name:
            raise ValueError("Sub-profile name cannot be empty")
        if new_name == self.DEFAULT_NAME:
            raise ValueError("Reserved name")
        store = self._sections.get(section, {})
        if old == self.DEFAULT_NAME:
            raise ValueError("Default sub-profile cannot be renamed")
        if old not in store:
            raise KeyError(old)
        if new_name in store:
            raise ValueError("Sub-profile already exists")
        store[new_name] = store.pop(old)
        cat_map = self._categories.setdefault(section, {})
        cat = cat_map.pop(old, self.CATEGORY_CUSTOM)
        cat_map[new_name] = cat
        self._write()

    def find_match(self, section: str, payload: dict) -> Optional[str]:
        store = self._sections.get(section, {})
        target = json.dumps(self._sanitize_profile(payload), sort_keys=True)
        for name, data in store.items():
            if json.dumps(data, sort_keys=True) == target:
                return name
        return None

