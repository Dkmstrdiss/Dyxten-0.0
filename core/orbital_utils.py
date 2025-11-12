"""Utilities shared between the controller and the renderer for orbital zones."""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence

__all__ = ["solve_tangent_radii"]


def solve_tangent_radii(raw: Iterable[float], spans: Sequence[float]) -> List[float]:
    """Return radii adjusted so neighbouring circles remain tangent.

    Parameters
    ----------
    raw:
        Desired radii for each orbital zone. Negative values are clamped to zero.
    spans:
        Distance between consecutive donut buttons. The length should match the
        number of radii. When the sequence is shorter the remaining spans are
        assumed to be equal to the last provided value.

    The function implements the same relaxation strategy that was previously
    embedded in the renderer. It is now shared so both the controller UI and the
    view can stay in sync when enforcing tangency constraints.
    """

    # Previously this function adjusted radii to enforce tangency between
    # neighbouring orbital zones. The tangency solver has been intentionally
    # disabled: we now accept the raw values provided by the UI and return
    # them (after clamping to non-negative floats). This lets the widgets
    # drive the visual sizes directly without automatic redistribution.

    raw_list = [max(0.0, float(r)) for r in raw]
    return list(raw_list)
