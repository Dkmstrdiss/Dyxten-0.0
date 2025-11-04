import copy
import hashlib
import json
import re
import shutil
import stat
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, List


def _slugify(name: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", name.strip().lower()).strip("-")
    return slug or "entry"


def _relocate_legacy_file(source: Path, destination: Path) -> Path:
    """Move a legacy flat-file to the structured storage location.

    When a previous version stored data inside a plain JSON file whose path now
    collides with the directory-based layout, we rename the file to the
    ``destination`` path (or to a suffixed variant if it already exists) so the
    directory can be created without raising ``FileExistsError``.
    """

    if not source.exists() or source.is_dir():
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    target = destination
    stem = destination.stem if destination.suffix else destination.name
    suffix = destination.suffix
    counter = 0
    while target.exists():
        counter += 1
        if suffix:
            target = destination.with_name(f"{stem}.legacy{counter}{suffix}")
        else:
            target = destination.with_name(f"{stem}.legacy{counter}")

    try:
        source.replace(target)
    except OSError:
        shutil.copy2(str(source), str(target))

        def _ensure_removed(path: Path) -> None:
            try:
                path.unlink()
                return
            except FileNotFoundError:
                return
            except PermissionError:
                try:
                    path.chmod(stat.S_IWRITE | stat.S_IREAD)
                    path.unlink()
                    return
                except OSError:
                    pass
            except OSError:
                pass

            stem = path.stem if path.suffix else path.name
            suffix = path.suffix
            counter = 0
            while True:
                counter += 1
                if suffix:
                    candidate = path.with_name(f"{stem}.stale{counter}{suffix}")
                else:
                    candidate = path.with_name(f"{stem}.stale{counter}")
                if candidate.exists():
                    continue
                try:
                    path.rename(candidate)
                except OSError:
                    break
                else:
                    break

        _ensure_removed(source)

    return target

try:
    from .config import DEFAULTS, PROFILE_PRESETS, SUBPROFILE_PRESETS
except ImportError:  # pragma: no cover
    from core.control.config import DEFAULTS, PROFILE_PRESETS, SUBPROFILE_PRESETS


class ProfileManager:
    """Persist and retrieve parameter profiles."""

    DEFAULT_PROFILE = "Default"

    def __init__(self, storage_path: Optional[Path] = None):
        base_dir = Path.home() / ".dyxten"
        raw_path = Path(storage_path) if storage_path is not None else (base_dir / "profiles")
        if raw_path.suffix:
            self._legacy_file = raw_path
            self.path = raw_path.parent / raw_path.stem
        else:
            self.path = raw_path
            self._legacy_file = raw_path.with_suffix(".json")
        if self.path.exists() and self.path.is_file():
            self._legacy_file = _relocate_legacy_file(self.path, self._legacy_file)
        self._profiles: Dict[str, dict] = {}
        self._profile_dirs: Dict[str, Path] = {}
        self._load()

    # ------------------------------------------------------------------ utils
    def _load(self) -> None:
        self._profiles = {}
        self._profile_dirs = {}

        if self.path.is_dir():
            for entry in sorted(self.path.iterdir()):
                if not entry.is_dir():
                    continue
                name = entry.name
                meta_path = entry / "metadata.json"
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        if isinstance(meta, dict) and isinstance(meta.get("name"), str):
                            name = meta["name"]
                    except Exception:
                        pass
                sections: Dict[str, dict] = {}
                for section_file in entry.glob("*.json"):
                    if section_file.name == "metadata.json":
                        continue
                    try:
                        payload = json.loads(section_file.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if isinstance(payload, dict):
                        sections[section_file.stem] = copy.deepcopy(payload)
                if sections:
                    self._profiles[name] = sections
                    self._profile_dirs[name] = entry

        if not self._profiles and self._legacy_file.exists():
            try:
                raw = json.loads(self._legacy_file.read_text(encoding="utf-8"))
            except Exception:
                raw = {}
            if isinstance(raw, dict):
                self._profiles = {
                    str(name): self._sanitize_profile(data)
                    for name, data in raw.items()
                    if isinstance(data, dict)
                }
                self._write()

        changed = self.ensure_default(DEFAULTS)
        if self.ensure_presets(PROFILE_PRESETS):
            changed = True
        if changed:
            self._write()

    def _write(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        existing_dirs = {entry for entry in self.path.iterdir() if entry.is_dir()}
        used_dirs = set()
        for name in sorted(self._profiles.keys(), key=str.lower):
            directory = self._profile_dirs.get(name)
            if directory is None:
                directory = self._build_profile_dir(name)
            used_dirs.add(directory)
            self._write_profile_dir(directory, name, self._profiles[name])
            self._profile_dirs[name] = directory
        for directory in existing_dirs - used_dirs:
            shutil.rmtree(directory, ignore_errors=True)

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

    def _build_profile_dir(self, name: str) -> Path:
        slug = _slugify(name) or "profile"
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        return self.path / f"{slug}-{digest}"

    def _write_profile_dir(self, directory: Path, name: str, payload: dict) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        metadata = {"name": name}
        (directory / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        existing = {
            path
            for path in directory.glob("*.json")
            if path.name != "metadata.json"
        }
        used = set()
        for section in sorted(payload.keys()):
            values = payload[section]
            if not isinstance(values, dict):
                continue
            section_path = directory / f"{section}.json"
            section_path.write_text(
                json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            used.add(section_path)
        for leftover in existing - used:
            try:
                leftover.unlink()
            except FileNotFoundError:
                pass

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
            directory = self._profile_dirs.pop(name, None)
            if directory is not None and directory.exists():
                shutil.rmtree(directory, ignore_errors=True)
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
        payload = self._profiles.pop(old)
        directory = self._profile_dirs.pop(old, None)
        self._profiles[new_name] = payload
        if directory is not None and directory.exists():
            new_dir = self._build_profile_dir(new_name)
            if new_dir.exists():
                shutil.rmtree(new_dir, ignore_errors=True)
            directory.rename(new_dir)
            self._profile_dirs[new_name] = new_dir
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
        raw_path = Path(storage_path) if storage_path is not None else (base_dir / "subprofiles")
        if raw_path.suffix:
            self._legacy_file = raw_path
            self.path = raw_path.parent / raw_path.stem
        else:
            self.path = raw_path
            self._legacy_file = raw_path.with_suffix(".json")
        if self.path.exists() and self.path.is_file():
            self._legacy_file = _relocate_legacy_file(self.path, self._legacy_file)
        self._sections: Dict[str, Dict[str, dict]] = {}
        self._categories: Dict[str, Dict[str, str]] = {}
        self._subprofile_paths: Dict[Tuple[str, str], Path] = {}
        self._load()

    # ------------------------------------------------------------------ utils
    def _load(self) -> None:
        self._sections = {}
        self._categories = {}
        self._subprofile_paths = {}

        if self.path.is_dir():
            for section_dir in sorted(self.path.iterdir()):
                if not section_dir.is_dir():
                    continue
                section_name = section_dir.name
                store: Dict[str, dict] = {}
                cat_map: Dict[str, str] = {}
                for preset_file in section_dir.glob("*.json"):
                    try:
                        data = json.loads(preset_file.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if not isinstance(data, dict):
                        continue
                    name = data.get("name") if isinstance(data.get("name"), str) else preset_file.stem
                    category = data.get("category") if isinstance(data.get("category"), str) else self.CATEGORY_CUSTOM
                    payload = data.get("payload") if isinstance(data.get("payload"), dict) else None
                    if payload is None:
                        payload = {
                            key: value
                            for key, value in data.items()
                            if key not in {"name", "category"}
                        }
                    if not isinstance(payload, dict):
                        continue
                    store[name] = self._sanitize_profile(payload)
                    cat_map[name] = category
                    self._subprofile_paths[(section_name, name)] = preset_file
                if store:
                    self._sections[section_name] = store
                    self._categories[section_name] = cat_map

        if not self._sections and self._legacy_file.exists():
            try:
                raw = json.loads(self._legacy_file.read_text(encoding="utf-8"))
            except Exception:
                raw = {}
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
                self._write()

        for section, store in self._sections.items():
            cat_map = self._categories.setdefault(section, {})
            for name in store.keys():
                cat_map.setdefault(name, self.CATEGORY_CUSTOM)

        changed = False
        if self._write_defaults():
            changed = True
        if self._migrate_distribution_payloads():
            changed = True
        if changed:
            self._write()

    def _write(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        existing_sections = {entry for entry in self.path.iterdir() if entry.is_dir()}
        used_sections = set()
        for section in sorted(self._sections.keys()):
            store = self._sections[section]
            section_dir = self.path / section
            used_sections.add(section_dir)
            section_dir.mkdir(parents=True, exist_ok=True)
            existing_files = {path for path in section_dir.glob("*.json")}
            used_files = set()
            cat_map = self._categories.get(section, {})
            for name in sorted(store.keys(), key=str.lower):
                payload = store[name]
                if not isinstance(payload, dict):
                    continue
                target_path = self._subprofile_paths.get((section, name))
                if target_path is None or target_path.parent != section_dir:
                    target_path = self._build_subprofile_path(section, name)
                entry = {
                    "name": name,
                    "category": cat_map.get(name, self.CATEGORY_CUSTOM),
                    "payload": payload,
                }
                target_path.write_text(
                    json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                used_files.add(target_path)
                self._subprofile_paths[(section, name)] = target_path
            for leftover in existing_files - used_files:
                try:
                    leftover.unlink()
                except FileNotFoundError:
                    pass
        for section_dir in existing_sections - used_sections:
            shutil.rmtree(section_dir, ignore_errors=True)

    def _migrate_distribution_payloads(self) -> bool:
        store = self._sections.get("distribution")
        if not isinstance(store, dict):
            return False
        changed = False
        for name, payload in list(store.items()):
            if not isinstance(payload, dict):
                continue
            if "distribution" in payload and isinstance(payload["distribution"], dict):
                flattened = self._sanitize_profile(payload["distribution"])
                store[name] = flattened
                changed = True
            elif any(key in payload for key in ("mask", "distribution")):
                # Remove unexpected wrappers while preserving existing scalar keys.
                store[name] = self._sanitize_profile(
                    {
                        key: value
                        for key, value in payload.items()
                        if key not in {"mask"}
                    }
                )
                changed = True
        return changed

    def _record_category(self, section: str, name: str, category: str) -> None:
        self._categories.setdefault(section, {})[name] = category

    def _build_subprofile_path(self, section: str, name: str) -> Path:
        slug = _slugify(name) or "preset"
        digest = hashlib.sha1(f"{section}:{name}".encode("utf-8")).hexdigest()[:8]
        return self.path / section / f"{slug}-{digest}.json"

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

    @staticmethod
    def _dict_subset(target: dict, template: dict) -> bool:
        for key, value in template.items():
            if isinstance(value, dict):
                child = target.get(key)
                if not isinstance(child, dict):
                    return False
                if not SubProfileManager._dict_subset(child, value):
                    return False
            else:
                if target.get(key) != value:
                    return False
        return True

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
        self._subprofile_paths[(section, clean_name)] = self._build_subprofile_path(section, clean_name)
        self._write()

    def set_default(self, section: str, payload: dict) -> None:
        """Override the default payload for a section."""

        store = self._sections.setdefault(section, {})
        store[self.DEFAULT_NAME] = self._sanitize_profile(payload)
        self._record_category(section, self.DEFAULT_NAME, self.CATEGORY_DEFAULT)
        self._subprofile_paths[(section, self.DEFAULT_NAME)] = self._build_subprofile_path(section, self.DEFAULT_NAME)
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
            path = self._subprofile_paths.pop((section, name), None)
            if path is not None and path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
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
        payload = store.pop(old)
        store[new_name] = payload
        cat_map = self._categories.setdefault(section, {})
        cat = cat_map.pop(old, self.CATEGORY_CUSTOM)
        cat_map[new_name] = cat
        path = self._subprofile_paths.pop((section, old), None)
        new_path = self._build_subprofile_path(section, new_name)
        if path is not None and path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        self._subprofile_paths[(section, new_name)] = new_path
        self._write()

    def find_match(self, section: str, payload: dict) -> Optional[str]:
        store = self._sections.get(section, {})
        target = self._sanitize_profile(payload)
        for name, data in store.items():
            if self._dict_subset(target, data):
                return name
        return None

