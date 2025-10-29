"""Registry for linkable controls used by the controller tab."""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from functools import partial
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from PyQt5 import QtCore, QtWidgets

try:  # pragma: no cover - sip is optional
    from sip import isdeleted as _sip_isdeleted
except ImportError:  # pragma: no cover - fallback when sip is unavailable
    def _sip_isdeleted(_obj) -> bool:
        return False


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


class LinkRegistry(QtCore.QObject):
    """Centralised store for linkable widgets across the application."""

    selectionChanged = QtCore.pyqtSignal()
    registryChanged = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self._controls: Dict[int, LinkableControl] = {}
        self._selected_order: List[int] = []
        self._by_identifier: Dict[str, int] = {}
        self._alive = True
        self.destroyed.connect(self._mark_destroyed)

    # ------------------------------------------------------------------ utils
    def register(self, widget: QtWidgets.QWidget, control: LinkableControl) -> None:
        widget_id = id(widget)
        existing = self._controls.get(widget_id)
        if existing is not None:
            self._controls[widget_id] = control
            self._by_identifier[control.identifier] = widget_id
            self.registryChanged.emit()
            return

        self._controls[widget_id] = control
        self._by_identifier[control.identifier] = widget_id

        ref = weakref.ref(widget)
        widget.destroyed.connect(partial(self._on_widget_destroyed, widget_id, ref))
        widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(partial(self._show_menu, widget_id))
        widget.setProperty("dyxten_link_selected", False)

        self.registryChanged.emit()

    def unregister(self, widget: QtWidgets.QWidget) -> None:
        widget_id = id(widget)
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
        if widget_id in self._selected_order:
            self._selected_order.remove(widget_id)
            self.selectionChanged.emit()
        self.registryChanged.emit()

    def _mark_destroyed(self, *args) -> None:  # pragma: no cover - Qt lifecycle callback
        self._alive = False

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
        if widget_id in self._selected_order:
            act = menu.addAction("Retirer du contrôleur")
            act.triggered.connect(lambda: self.deselect_widget(widget_id))
        else:
            act = menu.addAction("Lier au contrôleur")
            act.triggered.connect(lambda: self.select_widget(widget_id))
        menu.addSeparator()
        info = menu.addAction(f"Onglet : {control.tab}")
        info.setEnabled(False)
        info2 = menu.addAction(f"Paramètre : {control.label}")
        info2.setEnabled(False)
        menu.exec_(global_pos)

    # ----------------------------------------------------------------- select
    def select_widget(self, widget_id: int) -> None:
        if widget_id not in self._controls:
            return
        if widget_id in self._selected_order:
            return
        self._selected_order.append(widget_id)
        self._update_widget_state(widget_id, True)
        self.selectionChanged.emit()

    def deselect_widget(self, widget_id: int) -> None:
        if widget_id not in self._selected_order:
            return
        self._selected_order.remove(widget_id)
        self._update_widget_state(widget_id, False)
        self.selectionChanged.emit()

    def clear_selection(self) -> None:
        if not self._selected_order:
            return
        for widget_id in list(self._selected_order):
            self._update_widget_state(widget_id, False)
        self._selected_order.clear()
        self.selectionChanged.emit()

    def selected_controls(self) -> List[LinkableControl]:
        out: List[LinkableControl] = []
        for widget_id in list(self._selected_order):
            control = self._controls.get(widget_id)
            if control is None:
                continue
            out.append(control)
        return out

    def set_selection(self, identifiers: Iterable[str]) -> None:
        ids = [self._by_identifier.get(ident) for ident in identifiers]
        ids = [wid for wid in ids if wid is not None]
        if set(ids) == set(self._selected_order):
            return
        for widget_id in list(self._selected_order):
            self._update_widget_state(widget_id, False)
        self._selected_order = []
        for widget_id in ids:
            if widget_id not in self._controls:
                continue
            self._selected_order.append(widget_id)
            self._update_widget_state(widget_id, True)
        self.selectionChanged.emit()

    def ensure_selection(self, identifiers: Iterable[str]) -> None:
        missing = False
        for ident in identifiers:
            if ident not in self._by_identifier:
                missing = True
                break
        if missing:
            return
        self.set_selection(identifiers)

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

    def deselect_identifier(self, identifier: str) -> None:
        widget_id = self._by_identifier.get(identifier)
        if widget_id is None:
            return
        self.deselect_widget(widget_id)


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

