"""Dynamic topology library loaded from JSON files.

This module centralises the loading of procedural topology definitions stored
as JSON documents.  Each JSON file is expected to contain a ``geometry``
object describing the default parameters along with a ``code`` string defining
the generator implementation.  The registry scans the ``topologie`` directory
and exposes utility helpers so the rest of the application can discover,
instantiate, import or export those definitions without hard-coding them in
Python modules.

The goal is to make it straightforward to add new topologies simply by dropping
JSON files in the directory (or importing them at runtime) while keeping the
rest of the application agnostic of the storage format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPOLOGY_DIR = ROOT / "topologie"


def _ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _category_from_path(root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return "Bibliothèque JSON"
    parts = [part for part in relative.parts[:-1] if part not in (".", "")]
    if not parts:
        return "Bibliothèque JSON"
    return " / ".join(parts)


@dataclass(slots=True)
class TopologyDefinition:
    """Representation of a topology described in a JSON file."""

    name: str
    path: Path
    geometry: Dict[str, Any]
    code: str
    category: str
    description: str
    label: str
    parameter_names: Tuple[str, ...]

    @property
    def defaults(self) -> Dict[str, Any]:
        """Return the default geometry parameters without the code snippet."""

        return {
            key: value
            for key, value in self.geometry.items()
            if key not in {"code", "topology"}
        }

    @property
    def parameters(self) -> Tuple[str, ...]:
        """Return the ordered parameter names used by the topology."""

        if self.parameter_names:
            return self.parameter_names
        names: List[str] = []
        for key in self.geometry.keys():
            if key in {"code", "topology"}:
                continue
            if isinstance(key, str):
                names.append(key)
        return tuple(names)

    def raw_payload(self) -> Dict[str, Any]:
        """Return the JSON serialisable payload for export."""

        payload: Dict[str, Any] = {"geometry": dict(self.geometry)}
        meta: Dict[str, Any] = {}
        if self.category:
            meta["category"] = self.category
        if self.description:
            meta["description"] = self.description
        if self.label:
            meta["label"] = self.label
        if self.parameter_names:
            meta["parameters"] = list(self.parameter_names)
        if meta:
            payload["meta"] = meta
        return payload

    def build_generator(self) -> Callable[[Mapping[str, Any], int], List[Tuple[float, float, float]]]:
        """Compile the user provided code and expose it as a callable."""

        namespace: Dict[str, Any] = {"__builtins__": __builtins__}
        exec(self.code, namespace)
        func_name = f"generate_{self.name}_geometry"
        candidate = namespace.get(func_name)
        if not callable(candidate):
            # Fall back to the first callable defined in the namespace.
            for value in namespace.values():
                if callable(value):
                    candidate = value
                    break
        if not callable(candidate):
            raise ValueError(f"Impossible de construire la topologie {self.name}: fonction introuvable")

        def _generator(params: Mapping[str, Any], cap: int) -> List[Tuple[float, float, float]]:
            combined: Dict[str, Any] = dict(self.defaults)
            combined.update(params)

            def _as_positive_int(value: Any) -> int:
                try:
                    number = int(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return 0
                return number if number > 0 else 0

            requested = _as_positive_int(combined.get("N"))
            default_n = _as_positive_int(self.defaults.get("N"))
            cap_n = _as_positive_int(cap)
            target = requested or default_n or cap_n or 4096
            if cap_n:
                target = min(target, cap_n)
            combined["N"] = target

            points = candidate(combined, target)
            out: List[Tuple[float, float, float]] = []
            for item in points:
                if isinstance(item, (tuple, list)) and len(item) >= 3:
                    try:
                        x = float(item[0])
                        y = float(item[1])
                        z = float(item[2])
                    except (TypeError, ValueError):
                        continue
                    out.append((x, y, z))
                    continue
                if hasattr(item, "x") and hasattr(item, "y") and hasattr(item, "z"):
                    try:
                        x = float(getattr(item, "x"))
                        y = float(getattr(item, "y"))
                        z = float(getattr(item, "z"))
                    except (TypeError, ValueError):
                        continue
                    out.append((x, y, z))
            return out[:target] if len(out) > target else out

        return _generator


class TopologyLibrary:
    """Registry responsible for loading, importing and exporting topologies."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = _ensure_directory(directory or DEFAULT_TOPOLOGY_DIR)
        self._definitions: Dict[str, TopologyDefinition] = {}
        self._categories: Dict[str, List[TopologyDefinition]] = {}
        self._category_order: List[str] = []
        self.reload()

    # ------------------------------------------------------------------ loading
    def reload(self) -> None:
        """Reload every topology available in the directory."""

        self._definitions.clear()
        self._categories.clear()
        self._category_order = []
        for path in sorted(self.directory.glob('**/*.json')):
            if not path.is_file():
                continue
            definition = self._load_file(path)
            if definition is None:
                continue
            self._definitions[definition.name] = definition
            if definition.category not in self._categories:
                self._categories[definition.category] = []
                self._category_order.append(definition.category)
            self._categories[definition.category].append(definition)
        for definitions in self._categories.values():
            definitions.sort(key=lambda item: item.label.lower())

    def _load_file(self, path: Path) -> Optional[TopologyDefinition]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        geometry = raw.get("geometry")
        if not isinstance(geometry, dict):
            return None
        name = str(geometry.get("topology") or path.stem)
        code = geometry.get("code")
        if not isinstance(code, str) or not code.strip():
            return None
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        raw_category = meta.get("category")
        if isinstance(raw_category, str) and raw_category.strip():
            category = raw_category.strip()
        else:
            category = _category_from_path(self.directory, path)
        raw_params = meta.get("parameters")
        parameter_names: Tuple[str, ...] = ()
        if isinstance(raw_params, (list, tuple)):
            parameter_names = tuple(
                str(param).strip()
                for param in raw_params
                if isinstance(param, str) and param.strip()
            )
        description = str(meta.get("description") or raw.get("description") or "")
        label = str(meta.get("label") or name)
        geometry_copy = dict(geometry)
        return TopologyDefinition(
            name=name,
            path=path,
            geometry=geometry_copy,
            code=code,
            category=category,
            description=description,
            label=label,
            parameter_names=parameter_names,
        )

    # ----------------------------------------------------------------- queries
    def definitions(self) -> Tuple[TopologyDefinition, ...]:
        return tuple(self._definitions.values())

    def get(self, name: str) -> Optional[TopologyDefinition]:
        return self._definitions.get(name)

    def names(self) -> Tuple[str, ...]:
        return tuple(self._definitions.keys())

    def iter(self) -> Iterator[TopologyDefinition]:
        return iter(self._definitions.values())

    def categories(self) -> Tuple[str, ...]:
        return tuple(self._category_order)

    def definitions_for_category(self, category: str) -> Tuple[TopologyDefinition, ...]:
        return tuple(self._categories.get(category, []))

    def grouped_definitions(self) -> Tuple[Tuple[str, Tuple[TopologyDefinition, ...]], ...]:
        return tuple((category, tuple(self._categories.get(category, []))) for category in self._category_order)

    # ----------------------------------------------------------- import/export
    def import_file(self, source: Path | str, *, overwrite: bool = False) -> TopologyDefinition:
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(source)
        definition = self._load_file(source_path)
        if definition is None:
            raise ValueError(f"Fichier topologie invalide: {source}")
        target_path = self.directory / source_path.name
        if target_path.exists() and not overwrite:
            raise FileExistsError(target_path)
        target_path.write_text(json.dumps(definition.raw_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.reload()
        refreshed = self.get(definition.name)
        if refreshed is None:
            raise ValueError(f"Impossible de recharger la topologie importée: {definition.name}")
        return refreshed

    def export_file(self, name: str, destination: Path | str) -> Path:
        definition = self.get(name)
        if definition is None:
            raise KeyError(name)
        dest_path = Path(destination)
        if dest_path.is_dir():
            dest_path = dest_path / definition.path.name
        dest_path.write_text(json.dumps(definition.raw_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
        return dest_path

    # -------------------------------------------------------------- generators
    def generators(self) -> Dict[str, Callable[[Mapping[str, Any], int], List[Tuple[float, float, float]]]]:
        out: Dict[str, Callable[[Mapping[str, Any], int], List[Tuple[float, float, float]]]] = {}
        for definition in self._definitions.values():
            try:
                out[definition.name] = definition.build_generator()
            except Exception:
                continue
        return out


_LIBRARY: Optional[TopologyLibrary] = None


def get_topology_library() -> TopologyLibrary:
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = TopologyLibrary()
    return _LIBRARY


__all__ = ["TopologyDefinition", "TopologyLibrary", "get_topology_library"]
