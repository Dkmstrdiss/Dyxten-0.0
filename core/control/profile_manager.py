"""Minimal profile manager used by the control window during development.

This implementation is intentionally small and conservative: it stores
profiles as JSON files under a `profiles/` directory at the repository root
and exposes the small set of methods expected by `ControlWindow`.

It is a safe stub — behaviour can be replaced later with a fuller
implementation or restored from source control.
"""
from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Dict, Iterable, Optional

try:
    from .config import DEFAULTS  # type: ignore
except Exception:  # pragma: no cover - defensive fallback
    DEFAULTS = {}

ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = ROOT / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


DEFAULT_PROFILE = "Default"


class ProfileManager:
    """Small file-backed profile manager.

    Profiles are saved as JSON files in ``profiles/<name>.json``. The class
    provides only the methods used by the control window so it is safe to
    replace later with a more advanced implementation.
    """

    DEFAULT_PROFILE = DEFAULT_PROFILE

    def __init__(self) -> None:
        # nothing heavy to initialise
        pass

    def _path_for(self, name: str) -> Path:
        return PROFILES_DIR / f"{name}.json"

    def list_profiles(self) -> Iterable[str]:
        names = [p.stem for p in PROFILES_DIR.glob("*.json") if p.is_file()]
        # ensure the default profile is always available
        if DEFAULT_PROFILE not in names:
            names.insert(0, DEFAULT_PROFILE)
        return sorted(names)

    def get_profile(self, name: str) -> Dict:
        if name == DEFAULT_PROFILE:
            return copy.deepcopy(DEFAULTS)
        path = self._path_for(name)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # Fallback to defaults if file missing or invalid
            return copy.deepcopy(DEFAULTS)

    def save_profile(self, name: str, state: Dict) -> None:
        path = self._path_for(name)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def has_profile(self, name: str) -> bool:
        if name == DEFAULT_PROFILE:
            return True
        return self._path_for(name).is_file()

    def delete_profile(self, name: str) -> None:
        path = self._path_for(name)
        if path.is_file():
            path.unlink()
        else:
            raise FileNotFoundError(name)

    def rename_profile(self, old: str, new: str) -> None:
        old_path = self._path_for(old)
        new_path = self._path_for(new)
        if not old_path.is_file():
            raise FileNotFoundError(old)
        if new_path.exists():
            raise FileExistsError(new_path)
        old_path.rename(new_path)

    def profile_equals(self, name: str, state: Dict) -> bool:
        try:
            stored = self.get_profile(name)
        except Exception:
            return False
        return stored == state


class SubProfileManager:
    """Tiny helper handling tab-level sub-profiles.

    The real application provides a more featureful manager; here we keep a
    simple namespaced store persisted in a JSON file so tabs can read/write
    their small sub-profiles during development.
    """

    _STORE_FILE = PROFILES_DIR / "_subprofiles.json"

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Dict]] = {}
        self._load()

    # API expected by SubProfilePanel -------------------------------------------------
    DEFAULT_NAME = "Default"

    def ensure_section(self, namespace: str, defaults: Dict) -> None:
        """Ensure a section exists and has a default entry."""
        ns = self._data.setdefault(namespace, {})
        if self.DEFAULT_NAME not in ns:
            ns[self.DEFAULT_NAME] = copy.deepcopy(defaults or {})
            self._save()

    def list_grouped(self, namespace: str):
        """Return a list of (label, names) groups for the UI.

        We keep a single group labelled 'Saved' for simplicity.
        """
        names = sorted(list(self._data.get(namespace, {}).keys()))
        # Exclude header/empty names if present
        return [("Saved", names)] if names else []

    def find_match(self, namespace: str, payload: Dict) -> Optional[str]:
        """Return the name of a subprofile whose payload equals the given payload.

        Performs a deep comparison; returns the first matching name or None.
        """
        for name, data in self._data.get(namespace, {}).items():
            if data == payload:
                return name
        return None

    def get(self, namespace: str, name: str) -> Optional[Dict]:
        return copy.deepcopy(self._data.get(namespace, {}).get(name))

    def save(self, namespace: str, name: str, payload: Dict) -> None:
        self._data.setdefault(namespace, {})[name] = copy.deepcopy(payload)
        self._save()

    def rename(self, namespace: str, old: str, new: str) -> None:
        if old not in self._data.get(namespace, {}):
            raise FileNotFoundError(old)
        if new in self._data.get(namespace, {}):
            raise FileExistsError(new)
        self._data.setdefault(namespace, {})[new] = self._data[namespace].pop(old)
        self._save()

    def delete(self, namespace: str, name: str) -> None:
        if name in self._data.get(namespace, {}):
            del self._data[namespace][name]
            self._save()
        else:
            raise FileNotFoundError(name)

    def set_default(self, namespace: str, payload: Dict) -> None:
        self._data.setdefault(namespace, {})[self.DEFAULT_NAME] = copy.deepcopy(payload)
        self._save()

    # Public constant used by the UI code to identify the default entry name
    DEFAULT_NAME = "Default"

    def _load(self) -> None:
        try:
            if self._STORE_FILE.is_file():
                self._data = json.loads(self._STORE_FILE.read_text(encoding="utf-8"))
            else:
                self._data = {}
        except Exception:
            self._data = {}

    def _save(self) -> None:
        try:
            self._STORE_FILE.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def list_subprofiles(self, namespace: str) -> Iterable[str]:
        return sorted(list(self._data.get(namespace, {}).keys()))

    def get(self, namespace: str, name: str) -> Optional[Dict]:
        return copy.deepcopy(self._data.get(namespace, {}).get(name))

    def save(self, namespace: str, name: str, payload: Dict) -> None:
        self._data.setdefault(namespace, {})[name] = copy.deepcopy(payload)
        self._save()

    def has(self, namespace: str, name: str) -> bool:
        return name in self._data.get(namespace, {})

    def delete(self, namespace: str, name: str) -> None:
        if name in self._data.get(namespace, {}):
            del self._data[namespace][name]
            self._save()

    # ------------------------------------------------------------------ helpers expected by the UI
    def ensure_section(self, section: str, defaults: Dict) -> None:
        """Ensure a section exists and has a default entry.

        The UI calls this to guarantee a minimal set of subprofiles for a tab.
        """
        sec = self._data.setdefault(section, {})
        if self.DEFAULT_NAME not in sec:
            sec[self.DEFAULT_NAME] = copy.deepcopy(defaults or {})
            self._save()

    def list_grouped(self, section: str):
        """Return a list of (label, names) groups for the combo UI.

        We show the default as a separate group and put user entries under
        "Personnels". Empty groups are omitted.
        """
        sec = self._data.get(section, {})
        default = [self.DEFAULT_NAME] if self.DEFAULT_NAME in sec else []
        others = [n for n in sorted(sec.keys()) if n != self.DEFAULT_NAME]
        groups = []
        if default:
            groups.append(("Par défaut", default))
        if others:
            groups.append(("Personnels", others))
        return groups

    def find_match(self, section: str, payload: Dict) -> Optional[str]:
        """Return a name matching the given payload or None."""
        sec = self._data.get(section, {})
        for name, data in sec.items():
            if data == payload:
                return name
        return None

    def set_default(self, section: str, payload: Dict) -> None:
        sec = self._data.setdefault(section, {})
        sec[self.DEFAULT_NAME] = copy.deepcopy(payload)
        self._save()

    def rename(self, section: str, old: str, new: str) -> None:
        sec = self._data.get(section, {})
        if old not in sec:
            raise FileNotFoundError(old)
        if new in sec:
            raise FileExistsError(new)
        sec[new] = sec.pop(old)
        self._save()
