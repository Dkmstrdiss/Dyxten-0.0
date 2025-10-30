"""Utilities shared between the Qt controller and the web renderer for the donut UI."""

from __future__ import annotations

from typing import List, Optional, Sequence


DEFAULT_DONUT_BUTTON_COUNT = 10
_DEFAULT_RADIUS_RATIO = 0.35


def _make_button(idx: int, label: Optional[str] = None, *, button_id: Optional[int] = None) -> dict:
    """Return a normalized button payload."""
    clean_label = label if (label and label.strip()) else f"Bouton {idx}"
    clean_id = button_id if isinstance(button_id, int) else idx
    return {"id": clean_id, "label": clean_label.strip()}


def default_donut_buttons(count: int = DEFAULT_DONUT_BUTTON_COUNT) -> List[dict]:
    """Build a list of default donut buttons."""
    return [_make_button(i + 1) for i in range(max(1, count))]


def default_donut_config() -> dict:
    """Return the default configuration used by both the UI and the web view."""
    return {
        "buttons": default_donut_buttons(),
        "radiusRatio": _DEFAULT_RADIUS_RATIO,
    }


def _sanitize_buttons(buttons: Sequence[object]) -> List[dict]:
    sanitized: List[dict] = []
    for idx, entry in enumerate(buttons):
        slot = idx + 1
        if isinstance(entry, dict):
            label = str(entry.get("label") or entry.get("text") or entry.get("name") or "").strip()
            ident = entry.get("id")
            sanitized.append(_make_button(slot, label, button_id=ident if isinstance(ident, int) else None))
        elif isinstance(entry, str):
            sanitized.append(_make_button(slot, entry))
        elif entry is None:
            sanitized.append(_make_button(slot))
        if len(sanitized) >= DEFAULT_DONUT_BUTTON_COUNT:
            break
    while len(sanitized) < DEFAULT_DONUT_BUTTON_COUNT:
        sanitized.append(_make_button(len(sanitized) + 1))
    return sanitized


def sanitize_donut_state(payload: Optional[dict]) -> dict:
    """Return a sanitized donut state based on user-provided payload."""
    if not isinstance(payload, dict):
        return default_donut_config()

    base = default_donut_config()

    buttons = payload.get("buttons")
    if isinstance(buttons, Sequence):
        base["buttons"] = _sanitize_buttons(buttons)

    radius = payload.get("radiusRatio")
    if isinstance(radius, (int, float)):
        base["radiusRatio"] = max(0.05, min(0.9, float(radius)))

    return base


__all__ = [
    "DEFAULT_DONUT_BUTTON_COUNT",
    "default_donut_buttons",
    "default_donut_config",
    "sanitize_donut_state",
]
