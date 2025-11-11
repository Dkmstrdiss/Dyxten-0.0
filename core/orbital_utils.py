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

    raw_list = [max(0.0, float(r)) for r in raw]
    radii = list(raw_list)
    if not radii:
        return radii
    span_list = [float(s) for s in spans]
    if not span_list:
        span_list = [0.0]
    if len(span_list) < len(radii):
        span_list.extend([span_list[-1]] * (len(radii) - len(span_list)))

    limit_count = len(radii)

    for i in range(limit_count):
        prev_span = span_list[i - 1] if limit_count > 1 else span_list[0]
        next_span = span_list[i] if limit_count > 1 else span_list[0]
        max_radius = min(prev_span, next_span) * 0.5 if limit_count > 1 else span_list[0] * 0.5
        if math.isfinite(max_radius):
            radii[i] = min(radii[i], max_radius)

    for _ in range(12):
        changed = False
        for i in range(limit_count):
            j = (i + 1) % limit_count
            span = span_list[i]
            if not math.isfinite(span) or span <= 0.0:
                continue
            current_sum = radii[i] + radii[j]
            if abs(current_sum - span) <= 0.5:
                continue
            if current_sum > span:
                excess = (current_sum - span) / 2.0
                new_i = max(0.0, radii[i] - excess)
                new_j = max(0.0, radii[j] - excess)
                if abs(new_i - radii[i]) > 1e-3 or abs(new_j - radii[j]) > 1e-3:
                    radii[i], radii[j] = new_i, new_j
                    changed = True
            else:
                deficit = span - current_sum
                if deficit <= 1e-3:
                    continue
                head_i = max(0.0, raw_list[i] - radii[i])
                head_j = max(0.0, raw_list[j] - radii[j])
                add = min(deficit / 2.0, head_i, head_j)
                if add > 1e-3:
                    radii[i] += add
                    radii[j] += add
                    changed = True
        if not changed:
            break
    return radii
