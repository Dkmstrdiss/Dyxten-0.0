"""Registry for linkable controls used by the controller tab."""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from functools import partial
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from importlib import import_module

from PyQt5 import QtCore, QtWidgets


def _load_sip_isdeleted() -> Callable[[object], bool]:
    """Return a callable checking whether a Qt object has been deleted."""

    for module_name in ("PyQt5.sip", "sip"):
        try:  # pragma: no cover - sip is optional
            module = import_module(module_name)
        except ImportError:
            continue
        func = getattr(module, "isdeleted", None)
        if callable(func):
            return func  # type: ignore[return-value]

    def _fallback(_obj: object) -> bool:
        return False

    return _fallback


_sip_isdeleted = _load_sip_isdeleted()


Number = float


@dataclass
class LinkableControl:
    """Metadata describing a widget that can be animated by the controller."""

    widget: QtWidgets.QWidget
    section: str
    key: str
    label: str
    tab: str
    control_type: str
    value_getter: Callable[[], Number]
    value_setter: Callable[[Number], None]
    range_getter: Callable[[], Tuple[Number, Number]]
    value_type: type

    @property
    def identifier(self) -> str:
        return f"{self.section}.{self.key}"


TRACK_COUNT = 5


class LinkRegistry(QtCore.QObject):
    """Centralised store for linkable widgets across the application."""

    selectionChanged = QtCore.pyqtSignal()
    registryChanged = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self._controls: Dict[int, LinkableControl] = {}
        self._selected_order: Dict[int, List[int]] = {index: [] for index in range(TRACK_COUNT)}
        self._by_identifier: Dict[str, int] = {}
        self._widget_tracks: Dict[int, Set[int]] = {}
        self._alive = True
        self.destroyed.connect(self._mark_destroyed)

    # ------------------------------------------------------------------ utils
    def register(self, widget: QtWidgets.QWidget, control: LinkableControl) -> None:
        if not self._alive or _sip_isdeleted(self):
            return

        widget_id = id(widget)
        existing = self._controls.get(widget_id)
        if existing is not None:
            self._controls[widget_id] = control
            self._by_identifier[control.identifier] = widget_id
            self._emit_registry_changed()
            return

        self._controls[widget_id] = control
        self._by_identifier[control.identifier] = widget_id

        ref = weakref.ref(widget)
        widget.destroyed.connect(partial(self._on_widget_destroyed, widget_id, ref))
        widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(partial(self._show_menu, widget_id))
        widget.setProperty("dyxten_link_selected", False)

        self._emit_registry_changed()

    def unregister(self, widget: QtWidgets.QWidget) -> None:
        widget_id = id(widget)
        if not self._alive or _sip_isdeleted(self):
            return
        self._cleanup_widget(widget_id)

    def _on_widget_destroyed(self, widget_id: int, ref: weakref.ReferenceType) -> None:
        self._cleanup_widget(widget_id)

    def _cleanup_widget(self, widget_id: int) -> None:
        if not self._alive or _sip_isdeleted(self):
            return

        control = self._controls.pop(widget_id, None)
        if control is None:
            return
        self._by_identifier.pop(control.identifier, None)
        tracks = self._widget_tracks.pop(widget_id, set())
        for track in list(tracks):
            self._remove_from_track(widget_id, track, emit=False)
        if tracks:
            self._emit_selection_changed()
        self._emit_registry_changed()

    def _mark_destroyed(self, *args) -> None:  # pragma: no cover - Qt lifecycle callback
        self._alive = False

    def _safe_emit(self, signal: QtCore.pyqtSignal) -> None:
        if not self._alive or _sip_isdeleted(self):
            return
        try:
            signal.emit()
        except RuntimeError:
            pass

    def _emit_registry_changed(self) -> None:
        self._safe_emit(self.registryChanged)

    def _emit_selection_changed(self) -> None:
        self._safe_emit(self.selectionChanged)

    def _update_widget_state(self, widget_id: int, selected: bool) -> None:
        control = self._controls.get(widget_id)
        if control is None:
            return
        widget = control.widget
        if widget is None:
            return
        widget.setProperty("dyxten_link_selected", selected)
        try:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        except Exception:
            pass

    def _show_menu(self, widget_id: int, pos: QtCore.QPoint) -> None:
        control = self._controls.get(widget_id)
        if control is None:
            return
        widget = control.widget
        if widget is None:
            return
        global_pos = widget.mapToGlobal(pos)
        menu = QtWidgets.QMenu(widget)
        tracks = self._widget_tracks.get(widget_id, set())
        add_menu = menu.addMenu("Lier au contrôleur")
        for track_index in range(TRACK_COUNT):
            if track_index in tracks:
                continue
            act = add_menu.addAction(f"Piste {track_index + 1}")
            act.triggered.connect(lambda _=False, t=track_index: self.select_widget(widget_id, t))
        if not add_menu.actions():
            add_menu.setEnabled(False)

        if tracks:
            remove_menu = menu.addMenu("Retirer du contrôleur")
            for track_index in sorted(tracks):
                act = remove_menu.addAction(f"Piste {track_index + 1}")
                act.triggered.connect(
                    lambda _=False, t=track_index: self.deselect_widget(widget_id, t)
                )
            remove_all = remove_menu.addAction("Retirer de toutes les pistes")
            remove_all.triggered.connect(lambda: self.deselect_widget(widget_id))
        else:
            remove_menu = menu.addMenu("Retirer du contrôleur")
            remove_menu.setEnabled(False)
        menu.addSeparator()
        info = menu.addAction(f"Onglet : {control.tab}")
        info.setEnabled(False)
        info2 = menu.addAction(f"Paramètre : {control.label}")
        info2.setEnabled(False)
        menu.exec_(global_pos)

    # ----------------------------------------------------------------- select
    def _ensure_track(self, track: int) -> Optional[int]:
        if track < 0 or track >= TRACK_COUNT:
            return None
        return track

    def _remove_from_track(self, widget_id: int, track: int, emit: bool = True) -> None:
        track_list = self._selected_order.get(track)
        if track_list is None:
            return
        if widget_id not in track_list:
            return
        track_list.remove(widget_id)
        tracks = self._widget_tracks.get(widget_id)
        if tracks is not None:
            tracks.discard(track)
            if not tracks:
                self._widget_tracks.pop(widget_id, None)
        remaining = bool(self._widget_tracks.get(widget_id))
        self._update_widget_state(widget_id, remaining)
        if emit:
            self._emit_selection_changed()

    def select_widget(self, widget_id: int, track: int = 0) -> None:
        if widget_id not in self._controls:
            return
        track = self._ensure_track(track)
        if track is None:
            return
        track_list = self._selected_order[track]
        if widget_id in track_list:
            return
        # remove from any other track to avoid duplicates
        current_tracks = self._widget_tracks.get(widget_id, set()).copy()
        for other_track in current_tracks:
            if other_track != track:
                self._remove_from_track(widget_id, other_track, emit=False)
        track_list.append(widget_id)
        self._widget_tracks.setdefault(widget_id, set()).add(track)
        self._update_widget_state(widget_id, True)
        self._emit_selection_changed()

    def deselect_widget(self, widget_id: int, track: Optional[int] = None) -> None:
        if track is None:
            tracks = list(self._widget_tracks.get(widget_id, set()))
            if not tracks:
                return
            for track_index in tracks:
                self._remove_from_track(widget_id, track_index, emit=False)
            self._emit_selection_changed()
            return
        track = self._ensure_track(track)
        if track is None:
            return
        self._remove_from_track(widget_id, track, emit=True)

    def clear_selection(self, track: Optional[int] = None) -> None:
        if track is None:
            changed = False
            for track_index, track_list in self._selected_order.items():
                if not track_list:
                    continue
                for widget_id in list(track_list):
                    self._update_widget_state(widget_id, False)
                track_list.clear()
                changed = True
            self._widget_tracks.clear()
            if changed:
                self._emit_selection_changed()
            return

        track = self._ensure_track(track)
        if track is None:
            return
        track_list = self._selected_order.get(track)
        if not track_list:
            return
        for widget_id in list(track_list):
            self._widget_tracks.get(widget_id, set()).discard(track)
            if not self._widget_tracks.get(widget_id):
                self._widget_tracks.pop(widget_id, None)
                self._update_widget_state(widget_id, False)
        track_list.clear()
        self._emit_selection_changed()

    def selected_controls(self, track: Optional[int] = None) -> List[LinkableControl]:
        out: List[LinkableControl] = []
        if track is None:
            seen: Set[int] = set()
            for track_list in self._selected_order.values():
                for widget_id in track_list:
                    if widget_id in seen:
                        continue
                    seen.add(widget_id)
                    control = self._controls.get(widget_id)
                    if control is None:
                        continue
                    out.append(control)
            return out

        track = self._ensure_track(track)
        if track is None:
            return out
        for widget_id in list(self._selected_order.get(track, [])):
            control = self._controls.get(widget_id)
            if control is None:
                continue
            out.append(control)
        return out

    def set_selection(self, identifiers: Iterable[str], track: int = 0) -> None:
        track = self._ensure_track(track)
        if track is None:
            return
        ids = [self._by_identifier.get(ident) for ident in identifiers]
        ids = [wid for wid in ids if wid is not None]
        current = set(self._selected_order.get(track, []))
        if set(ids) == current:
            return
        for widget_id in list(self._selected_order.get(track, [])):
            self._remove_from_track(widget_id, track, emit=False)
        for widget_id in ids:
            if widget_id not in self._controls:
                continue
            self.select_widget(widget_id, track)
        self._emit_selection_changed()

    def ensure_selection(self, identifiers: Iterable[str], track: int = 0) -> None:
        missing = False
        for ident in identifiers:
            if ident not in self._by_identifier:
                missing = True
                break
        if missing:
            return
        self.set_selection(identifiers, track=track)

    # ----------------------------------------------------------------- lookup
    def identifier_for_widget(self, widget: QtWidgets.QWidget) -> Optional[str]:
        widget_id = id(widget)
        control = self._controls.get(widget_id)
        return control.identifier if control else None

    def control_by_identifier(self, identifier: str) -> Optional[LinkableControl]:
        widget_id = self._by_identifier.get(identifier)
        if widget_id is None:
            return None
        return self._controls.get(widget_id)

    def deselect_identifier(self, identifier: str, track: Optional[int] = None) -> None:
        widget_id = self._by_identifier.get(identifier)
        if widget_id is None:
            return
        self.deselect_widget(widget_id, track=track)

    def tracks_for_identifier(self, identifier: str) -> List[int]:
        widget_id = self._by_identifier.get(identifier)
        if widget_id is None:
            return []
        tracks = self._widget_tracks.get(widget_id, set())
        return sorted(tracks)

    def selected_identifiers(self, track: Optional[int] = None) -> List[str]:
        if track is None:
            seen: Set[int] = set()
            out: List[str] = []
            for track_list in self._selected_order.values():
                for widget_id in track_list:
                    if widget_id in seen:
                        continue
                    seen.add(widget_id)
                    control = self._controls.get(widget_id)
                    if control is None:
                        continue
                    out.append(control.identifier)
            return out
        track = self._ensure_track(track)
        if track is None:
            return []
        out: List[str] = []
        for widget_id in self._selected_order.get(track, []):
            control = self._controls.get(widget_id)
            if control is None:
                continue
            out.append(control.identifier)
        return out


LINK_REGISTRY = LinkRegistry()


def _default_range(widget: QtWidgets.QWidget) -> Tuple[Number, Number]:
    if hasattr(widget, "minimum") and hasattr(widget, "maximum"):
        try:
            return float(widget.minimum()), float(widget.maximum())
        except Exception:
            pass
    if hasattr(widget, "maximum"):
        try:
            limit = float(widget.maximum())
            return -limit, limit
        except Exception:
            pass
    return -1.0, 1.0


def register_linkable_widget(
    widget: QtWidgets.QWidget,
    *,
    section: str,
    key: str,
    tab: str,
    label: Optional[str] = None,
    control_type: Optional[str] = None,
    value_getter: Optional[Callable[[], Number]] = None,
    value_setter: Optional[Callable[[Number], None]] = None,
    range_getter: Optional[Callable[[], Tuple[Number, Number]]] = None,
    value_type: Optional[type] = None,
) -> None:
    """Register a widget so it can be controlled by the controller tab."""

    if widget is None:
        return

    if value_getter is None and hasattr(widget, "value"):
        try:
            value_getter = widget.value  # type: ignore[assignment]
        except Exception:
            value_getter = lambda: 0.0
    if value_setter is None and hasattr(widget, "setValue"):
        try:
            value_setter = widget.setValue  # type: ignore[assignment]
        except Exception:
            value_setter = lambda _value: None

    if value_getter is None or value_setter is None:
        return

    if label is None:
        label = widget.property("dyxten_form_label") or ""

    if control_type is None:
        if isinstance(widget, QtWidgets.QDial):
            control_type = "dial"
        elif isinstance(widget, QtWidgets.QAbstractSlider):
            control_type = "slider"
        elif isinstance(widget, (QtWidgets.QDoubleSpinBox, QtWidgets.QSpinBox)):
            control_type = "spinbox"
        else:
            control_type = widget.metaObject().className()

    if range_getter is None:
        range_getter = partial(_default_range, widget)

    if value_type is None:
        try:
            sample = value_getter()
        except Exception:
            sample = 0
        if isinstance(sample, float):
            value_type = float
        else:
            value_type = int

    control = LinkableControl(
        widget=widget,
        section=section,
        key=key,
        label=str(label or key),
        tab=tab,
        control_type=control_type,
        value_getter=value_getter,
        value_setter=value_setter,
        range_getter=range_getter,
        value_type=value_type,
    )
    LINK_REGISTRY.register(widget, control)

