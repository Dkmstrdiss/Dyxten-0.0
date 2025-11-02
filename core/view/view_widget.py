"""Pure Python replacement for the historical JavaScript canvas renderer.

The original application embedded a large ``script.js`` file inside a
``QWebEngineView``.  The control window pushed JSON parameters to that script
which then generated the point cloud and rendered it on an HTML5 canvas.  This
module re-implements the same behaviour with standard Python code so the view
window no longer depends on an embedded browser.

Only a very small portion of the original project interacts with the renderer:

* ``ControlWindow.push_params`` sends the whole application state.
* ``ControlWindow`` expects a ``set_transparent`` method to toggle the window
  background.

This module exposes :func:`DyxtenViewWidget`, a factory returning a widget that
implements the ``set_params`` method mirroring the JavaScript API.  The widget
keeps the same data-model as the web version which greatly simplifies
interoperability with the existing controller code while allowing multiple
rendering backends.

The implementation favours a direct translation of the JavaScript logic to keep
behaviour parity.  The goal is not to micro-optimise the renderer but to offer
feature completeness and ease of maintenance.
"""

from __future__ import annotations

import math
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from ..donut import DEFAULT_DONUT_BUTTON_COUNT, default_donut_config, sanitize_donut_state
from ..topology_generators import (
    Point3D,
    BUILTIN_GENERATORS,
    _rand_for_index,
    _gen_uv_sphere,
    _value_noise3,
)

try:
    from ..topology_registry import get_topology_library
except ImportError:  # pragma: no cover - compat exécution directe
    from core.topology_registry import get_topology_library  # type: ignore


GeometryGenerator = Callable[[Mapping[str, object], int], List["Point3D"]]

__all__ = ["DyxtenViewWidget"]

# ---------------------------------------------------------------------------
# Data structures


@dataclass
class RenderItem:
    """Structure describing a point projected on screen."""

    sx: float
    sy: float
    r: float
    color: QtGui.QColor
    alpha: float
    depth: float
    world: Point3D


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def to_rad(deg: float) -> float:
    return deg * math.pi / 180.0


def _map_blend_mode(name: str | None) -> QtGui.QPainter.CompositionMode:
    mode = (name or "").lower()
    mapping = {
        "source": QtGui.QPainter.CompositionMode_Source,
        "normal": QtGui.QPainter.CompositionMode_SourceOver,
        "source-over": QtGui.QPainter.CompositionMode_SourceOver,
        "screen": QtGui.QPainter.CompositionMode_Screen,
        "lighten": QtGui.QPainter.CompositionMode_Lighten,
        "lighter": QtGui.QPainter.CompositionMode_Plus,
        "multiply": QtGui.QPainter.CompositionMode_Multiply,
        "add": QtGui.QPainter.CompositionMode_Plus,
        "additive": QtGui.QPainter.CompositionMode_Plus,
        "plus": QtGui.QPainter.CompositionMode_Plus,
    }
    return mapping.get(mode, QtGui.QPainter.CompositionMode_SourceOver)


# ---------------------------------------------------------------------------
# Utility helpers translated from the JavaScript implementation


def _sgnpow(u: float, p: float) -> float:
    a = abs(u)
    expo = 2.0 / max(1e-6, p)
    return math.copysign(a ** expo, u)

















def _default_state() -> Dict[str, dict]:
    return {
        "camera": {
            "camRadius": 20.0,
            "camHeightDeg": 15,
            "camTiltDeg": 0,
            "omegaDegPerSec": 20,
            "fov": 50,
        },
        "geometry": {
            "topology": "torus",
            "R": 1.0,
            "lat": 24,
            "lon": 24,
            "N": 250,
            "phi_g": 3.883222,
            "R_major": 1.2,
            "R_major2": 0.8,
            "r_minor": 0.45,
            "eps1": 1.0,
            "eps2": 1.0,
            "ax": 1.0,
            "ay": 1.0,
            "az": 1.0,
            "geo_level": 1,
            "mobius_w": 0.4,
            "arch_a": 0.0,
            "arch_b": 0.6,
            "theta_max": 6.28318,
            "log_a": 0.2,
            "log_b": 0.15,
            "rose_k": 4.0,
            "sf2_m": 6.0,
            "sf2_a": 1.0,
            "sf2_b": 1.0,
            "sf2_n1": 0.5,
            "sf2_n2": 0.5,
            "sf2_n3": 0.5,
            "density_pdf": "1",
            "poisson_dmin": 0.05,
            "lissajous_a": 3,
            "lissajous_b": 2,
            "lissajous_phase": 0.0,
            "vogel_k": 2.3999632,
            "se_n1": 1.0,
            "se_n2": 1.0,
            "half_height": 1.0,
            "noisy_amp": 0.1,
            "noisy_freq": 3.0,
            "noisy_gain": 1.0,
            "noisy_omega": 0.0,
            "sph_terms": "2,0,0.4;3,2,0.2",
            "weight_map": "1",
            "torus_knot_p": 3,
            "torus_knot_q": 2,
            "strip_w": 0.4,
            "strip_n": 2,
            "blob_noise_amp": 0.25,
            "blob_noise_scale": 2.0,
            "gyroid_scale": 1.0,
            "gyroid_thickness": 0.05,
            "gyroid_c": 0.0,
            "schwarz_scale": 1.0,
            "schwarz_iso": 0.0,
            "heart_scale": 1.0,
            "polyhedron_data": "",
            "poly_layers": 1,
            "poly_link_steps": 0,
            "metaballs_centers": "0,0,0",
            "metaballs_radii": "0.6",
            "metaballs_iso": 1.0,
            "df_ops": "sphere(1.0)",
            "sf3_m1": 3.0,
            "sf3_m2": 3.0,
            "sf3_m3": 3.0,
            "sf3_n1": 0.5,
            "sf3_n2": 0.5,
            "sf3_n3": 0.5,
            "sf3_a": 1.0,
            "sf3_b": 1.0,
            "sf3_scale": 1.0,
            "helix_r": 0.4,
            "helix_pitch": 0.3,
            "helix_turns": 3.0,
            "lissajous3d_Ax": 1.0,
            "lissajous3d_Ay": 1.0,
            "lissajous3d_Az": 1.0,
            "lissajous3d_wx": 3,
            "lissajous3d_wy": 2,
            "lissajous3d_wz": 5,
            "lissajous3d_phi": 0.0,
            "viviani_a": 1.0,
            "lic_N": 12,
            "lic_steps": 180,
            "lic_h": 0.05,
            "stream_N": 12,
            "stream_steps": 220,
            "geo_graph_level": 2,
            "rgg_nodes": 400,
            "rgg_radius": 0.2,
            "rings_count": 5,
            "ring_points": 96,
            "hex_step": 0.2,
            "hex_nx": 12,
            "hex_ny": 12,
            "voronoi_N": 50,
            "voronoi_bbox": "-1,1,-1,1",
        },
        "appearance": {
            "color": "#00C8FF",
            "colors": "#00C8FF@0,#FFFFFF@1",
            "opacity": 1.0,
            "px": 2.0,
            "palette": "uniform",
            "paletteK": 2,
            "h0": 200,
            "dh": 0,
            "wh": 0,
            "blendMode": "source-over",
            "shape": "circle",
            "alphaDepth": 0.0,
            "noiseScale": 1.0,
            "noiseSpeed": 0.0,
            "pxModMode": "none",
            "pxModAmp": 0,
            "pxModFreq": 0,
            "pxModPhaseDeg": 0,
        },
        "dynamics": {
            "rotX": 0,
            "rotY": 0,
            "rotZ": 0,
            "rotXMax": 360,
            "rotYMax": 360,
            "rotZMax": 360,
            "orientXDeg": 0,
            "orientYDeg": 0,
            "orientZDeg": 0,
            "pulseA": 0,
            "pulseW": 1,
            "pulsePhaseDeg": 0,
            "rotPhaseMode": "none",
            "rotPhaseDeg": 0,
        },
        "distribution": {
            "densityMode": "uniform",
            "sampler": "direct",
            "dmin": 0,
            "dmin_px": 0,
            "maskMode": "none",
            "maskSoftness": 0.2,
            "maskAnimate": 0,
            "noiseDistortion": 0,
            "densityPulse": 0,
            "clusterCount": 1,
            "clusterSpread": 0,
            "repelForce": 0,
            "noiseWarp": 0,
            "fieldFlow": 0,
            "pr": "uniform_area",
        },
        "mask": {
            "enabled": False,
            "mode": "none",
            "angleDeg": 30,
            "bandHalfDeg": 20,
            "lonCenterDeg": 0,
            "lonWidthDeg": 30,
            "softDeg": 10,
            "invert": False,
        },
        "system": {
            "Nmax": 50000,
            "dprClamp": 2.0,
            "depthSort": True,
            "transparent": True,
        },
        "donut": default_donut_config(),
    }


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = clamp01((x - edge0) / max(1e-6, edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)



def _spherical_from_cartesian(x: float, y: float, z: float) -> Tuple[float, float]:
    r = math.sqrt(x * x + y * y + z * z) or 1.0
    theta = math.acos(y / r)
    phi = math.atan2(z, x) % (2.0 * math.pi)
    return theta, phi


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        number = int(value, 16)
    except ValueError:
        return 0, 0, 0
    return (number >> 16) & 255, (number >> 8) & 255, number & 255


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _rgb_to_hsl(r: int, g: int, b: int) -> Tuple[float, float, float]:
    rf = r / 255.0
    gf = g / 255.0
    bf = b / 255.0
    max_v = max(rf, gf, bf)
    min_v = min(rf, gf, bf)
    l = (max_v + min_v) / 2.0
    if max_v == min_v:
        return 0.0, 0.0, l
    d = max_v - min_v
    s = d / (2.0 - max_v - min_v) if l > 0.5 else d / (max_v + min_v)
    if max_v == rf:
        h = (gf - bf) / d + (6.0 if gf < bf else 0.0)
    elif max_v == gf:
        h = (bf - rf) / d + 2.0
    else:
        h = (rf - gf) / d + 4.0
    h /= 6.0
    return h, s, l


def _hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
    def _hue(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        v = int(round(l * 255))
        return v, v, v
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = _hue(p, q, h + 1 / 3)
    g = _hue(p, q, h)
    b = _hue(p, q, h - 1 / 3)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def _mix_hex(color_a: str, color_b: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(color_a)
    r2, g2, b2 = _hex_to_rgb(color_b)
    h1, s1, l1 = _rgb_to_hsl(r1, g1, b1)
    h2, s2, l2 = _rgb_to_hsl(r2, g2, b2)
    h = h1 * (1 - t) + h2 * t
    s = s1 * (1 - t) + s2 * t
    l = l1 * (1 - t) + l2 * t
    rr, gg, bb = _hsl_to_rgb(h, s, l)
    return _rgb_to_hex(rr, gg, bb)


def _parse_gradient_stops(value: str | None) -> List[Tuple[str, float]]:
    if not value:
        return [("#00C8FF", 0.0), ("#FFFFFF", 1.0)]
    parts = [part.strip() for part in value.split(",") if part.strip()]
    raw: List[Tuple[str, Optional[float]]] = []
    for part in parts:
        if "@" in part:
            color, pos = part.split("@", 1)
            try:
                t = float(pos)
            except ValueError:
                t = None
            raw.append((color.strip(), t))
        else:
            raw.append((part, None))
    unspecified = [item for item in raw if item[1] is None]
    if unspecified:
        count = len(unspecified)
        for idx, item in enumerate(unspecified):
            raw[raw.index(item)] = (item[0], idx / max(1, count - 1))
    stops: List[Tuple[str, float]] = []
    for color, pos in raw:
        stops.append((color, clamp01(pos if pos is not None else 0.0)))
    stops.sort(key=lambda entry: entry[1])
    if stops[0][1] > 0:
        stops.insert(0, (stops[0][0], 0.0))
    if stops[-1][1] < 1:
        stops.append((stops[-1][0], 1.0))
    return stops


def _sample_gradient(stops: Sequence[Tuple[str, float]], t: float) -> str:
    t = clamp01(t)
    for idx in range(len(stops) - 1):
        color_a, pos_a = stops[idx]
        color_b, pos_b = stops[idx + 1]
        if pos_a <= t <= pos_b:
            local = (t - pos_a) / max(1e-6, pos_b - pos_a)
            return _mix_hex(color_a, color_b, local)
    return stops[-1][0]


def _enforce_min_distance(points: Sequence[Point3D], min_dist: float) -> List[Point3D]:
    if min_dist <= 0:
        return [p.copy() for p in points]
    cell = min_dist
    offsets = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)]
    grid: Dict[Tuple[int, int, int], List[Point3D]] = {}
    selected: List[Point3D] = []
    min_sq = min_dist * min_dist
    for point in points:
        ix = int(math.floor(point.x / cell))
        iy = int(math.floor(point.y / cell))
        iz = int(math.floor(point.z / cell))
        keep = True
        for dx, dy, dz in offsets:
            bucket = grid.get((ix + dx, iy + dy, iz + dz))
            if not bucket:
                continue
            for other in bucket:
                dxp = point.x - other.x
                dyp = point.y - other.y
                dzp = point.z - other.z
                if dxp * dxp + dyp * dyp + dzp * dzp < min_sq:
                    keep = False
                    break
            if not keep:
                break
        if not keep:
            continue
        selected.append(point.copy())
        grid.setdefault((ix, iy, iz), []).append(point)
    return selected if selected else [p.copy() for p in points]


class DyxtenEngine:
    """Small helper responsible for generating and animating the particle cloud."""

    _GEOMETRY_GENERATORS: Dict[str, GeometryGenerator] = {}

    def __init__(self) -> None:
        self.state: Dict[str, dict] = _default_state()
        self.gradient = _parse_gradient_stops(self.state["appearance"].get("colors"))
        self.base_points: List[Point3D] = []
        self._start_time = time.perf_counter()
        self._last_ms = 0.0
        self._cam_theta_deg = 0.0
        self._width = 1
        self._height = 1
        self._last_base_count = -1
        self._last_item_count = -1
        self._last_visible_count = -1
        self._last_avg_alpha = ""
        self._last_bounds = ""
        self._last_step_note = ""
        self.rebuild_geometry()

    # ------------------------------------------------------------------ helpers
    @property
    def now_ms(self) -> float:
        return (time.perf_counter() - self._start_time) * 1000.0

    def _debug(self, message: str) -> None:
        print(f"[Dyxten][DEBUG] {message}", flush=True)

    def merge_state(self, payload: Mapping[str, object]) -> None:
        for key, value in payload.items():
            if key == "donut":
                self.state["donut"] = sanitize_donut_state(value if isinstance(value, dict) else None)
                continue
            if key not in self.state or not isinstance(self.state[key], dict) or not isinstance(value, Mapping):
                self.state[key] = value  # type: ignore[assignment]
                continue
            for sub_key, sub_value in value.items():
                if isinstance(self.state[key].get(sub_key), dict) and isinstance(sub_value, Mapping):
                    self.state[key][sub_key].update(sub_value)  # type: ignore[index]
                else:
                    self.state[key][sub_key] = sub_value  # type: ignore[index]
        self.gradient = _parse_gradient_stops(self.state.get("appearance", {}).get("colors"))

    def set_params(self, payload: Mapping[str, object]) -> None:
        if not isinstance(payload, Mapping):
            return
        self.merge_state(payload)
        if any(key in payload for key in ("geometry", "distribution", "system")):
            self.rebuild_geometry()

    # ---------------------------------------------------------------- geometry
    def rebuild_geometry(self) -> None:
        geo = self.state.get("geometry", {})
        system = self.state.get("system", {})
        topology = geo.get("topology", "uv_sphere")
        generator = self._GEOMETRY_GENERATORS.get(topology, _gen_uv_sphere)
        cap = int(system.get("Nmax", 0) or 0)
        try:
            points = generator(geo, cap)
        except Exception:
            points = _gen_uv_sphere(geo, cap)
        if not points:
            self.base_points = []
            if self._last_base_count != 0:
                self._debug(
                    "rebuild_geometry produced 0 points (topology=%s, cap=%s, geo=%s)" % (topology, cap or "none", dict(geo))
                )
                self._last_base_count = 0
            return
        cx = sum(p.x for p in points) / len(points)
        cy = sum(p.y for p in points) / len(points)
        cz = sum(p.z for p in points) / len(points)
        centered = [Point3D(p.x - cx, p.y - cy, p.z - cz, idx) for idx, p in enumerate(points)]
        dist = self.state.get("distribution", {})
        dmin = float(dist.get("dmin", 0.0) or 0.0)
        if dmin > 0:
            centered = _enforce_min_distance(centered, dmin)
        self.base_points = centered
        count = len(centered)
        if count != self._last_base_count:
            self._debug(
                "rebuild_geometry generated %d points (topology=%s, cap=%s, dmin=%s)"
                % (count, topology, cap or "none", dmin)
            )
            self._last_base_count = count

    # ---------------------------------------------------------------- animation helpers
    def _apply_point_modifiers(self, base: Point3D, seed: int, now_ms: float) -> Point3D:
        g = self.state.get("geometry", {})
        dist = self.state.get("distribution", {})
        dyn = self.state.get("dynamics", {})
        R = float(g.get("R", 1.0) or 1.0)
        x, y, z = base.x, base.y, base.z

        noise_warp = float(dist.get("noiseWarp", 0.0) or 0.0)
        if noise_warp:
            amp = noise_warp * R * 0.4
            freq = 1.3
            anim = now_ms * 0.0006
            x += amp * (_value_noise3((base.x + anim) * freq, (base.y - anim) * freq, (base.z + 2 + anim) * freq) * 2 - 1)
            y += amp * (_value_noise3((base.x - anim) * freq, (base.y + anim) * freq, (base.z - anim) * freq) * 2 - 1)
            z += amp * (_value_noise3((base.x + anim * 0.5) * freq, (base.y + 2 * anim) * freq, (base.z - anim * 0.25) * freq) * 2 - 1)

        flow = float(dist.get("fieldFlow", 0.0) or 0.0)
        if flow:
            angle = (flow * 0.4 * now_ms * 0.001) + (flow * 0.3 * (y / max(1e-6, R)))
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            x, z = cos_a * x - sin_a * z, sin_a * x + cos_a * z

        repel = float(dist.get("repelForce", 0.0) or 0.0)
        if repel:
            r = math.sqrt(x * x + y * y + z * z) or 1.0
            diff = R - r
            k = repel * 0.6
            x += diff * k * (x / r)
            y += diff * k * (y / r)
            z += diff * k * (z / r)

        pulse = float(dist.get("densityPulse", 0.0) or 0.0)
        if pulse:
            scale = 1 + 0.3 * pulse * math.sin(now_ms * 0.001 * 2 * math.pi)
            x *= scale
            y *= scale
            z *= scale

        orient_x = dyn.get("orientXDeg") if dyn.get("orientXDeg") is not None else dist.get("orientXDeg")
        orient_y = dyn.get("orientYDeg") if dyn.get("orientYDeg") is not None else dist.get("orientYDeg")
        orient_z = dyn.get("orientZDeg") if dyn.get("orientZDeg") is not None else dist.get("orientZDeg")

        if orient_x:
            ox = to_rad(float(orient_x))
            cos_x, sin_x = math.cos(ox), math.sin(ox)
            y, z = cos_x * y - sin_x * z, sin_x * y + cos_x * z
        if orient_y:
            oy = to_rad(float(orient_y))
            cos_y, sin_y = math.cos(oy), math.sin(oy)
            x, z = cos_y * x + sin_y * z, -sin_y * x + cos_y * z
        if orient_z:
            oz = to_rad(float(orient_z))
            cos_z, sin_z = math.cos(oz), math.sin(oz)
            x, y = cos_z * x - sin_z * y, sin_z * x + cos_z * y

        return Point3D(x, y, z, seed)

    def _keep_point(self, point: Point3D, seed: int, now_ms: float) -> bool:
        dist = self.state.get("distribution", {})
        mode = dist.get("densityMode") or dist.get("pr") or "uniform"
        g = self.state.get("geometry", {})
        R = float(g.get("R", 1.0) or 1.0)
        weight = 1.0
        if mode == "centered":
            r_norm = math.sqrt(point.x * point.x + point.y * point.y + point.z * point.z) / max(1e-6, R)
            weight *= math.exp(-3 * r_norm * r_norm)
        elif mode == "edges":
            r_norm = math.sqrt(point.x * point.x + point.y * point.y + point.z * point.z) / max(1e-6, R)
            weight *= clamp01(r_norm ** 0.75)
        elif mode == "noise_field":
            n = _value_noise3(point.x * 1.6 + 11.1, point.y * 1.6 + 22.2, point.z * 1.6 + 33.3)
            weight *= clamp01(n)

        weight *= self._mask_weight(point, now_ms)
        weight = clamp01(weight)
        if weight <= 0:
            return False
        if weight >= 1:
            return True
        return _rand_for_index(seed + 1) <= weight

    def _mask_weight(self, point: Point3D, now_ms: float) -> float:
        mask = self.state.get("mask", {})
        if not mask.get("enabled") or mask.get("mode") == "none":
            return 1.0
        theta, phi = _spherical_from_cartesian(point.x, point.y, point.z)
        softness = float(mask.get("softDeg", 0.0) or 0.0)
        mode = mask.get("mode")
        if mode == "north_cap":
            cutoff = to_rad(float(mask.get("angleDeg", 30)))
            soft = to_rad(softness)
            w = _smoothstep(cutoff, cutoff + soft, theta)
            weight = 1 - w
        elif mode == "south_cap":
            cutoff = to_rad(float(mask.get("angleDeg", 30)))
            soft = to_rad(softness)
            w = _smoothstep(cutoff, cutoff + soft, math.pi - theta)
            weight = 1 - w
        elif mode == "equatorial_band":
            half = to_rad(float(mask.get("bandHalfDeg", 20)))
            soft = to_rad(softness)
            diff = abs(theta - math.pi / 2)
            weight = 1 - _smoothstep(half, half + soft, diff)
        elif mode == "longitudinal_band":
            center = to_rad(float(mask.get("lonCenterDeg", 0)))
            width = to_rad(float(mask.get("lonWidthDeg", 30)))
            soft = to_rad(softness)
            diff = abs((phi - center + math.pi) % (2 * math.pi) - math.pi)
            weight = 1 - _smoothstep(width / 2, width / 2 + soft, diff)
        else:
            weight = 1.0
        if mask.get("invert"):
            weight = 1 - weight
        return clamp01(weight)

    def _compute_phase_factor(self, point: Point3D, idx: int) -> float:
        dyn = self.state.get("dynamics", {})
        mode = dyn.get("rotPhaseMode", "none")
        if mode == "by_index":
            if len(self.base_points) <= 1:
                return 0.0
            return idx / (len(self.base_points) - 1)
        if mode == "by_radius":
            g = self.state.get("geometry", {})
            R = float(g.get("R", 1.0) or 1.0)
            return clamp01(math.sqrt(point.x * point.x + point.z * point.z) / max(1e-6, R))
        if mode == "random":
            return _rand_for_index(idx, 77)
        return 0.0

    def _pick_color(self, item: RenderItem, now_ms: float) -> QtGui.QColor:
        appearance = self.state.get("appearance", {})
        palette = appearance.get("palette", "uniform")
        if palette == "uniform":
            color = appearance.get("color", "#00C8FF")
        elif palette == "gradient_radial":
            dx = item.sx - self._width / 2
            dy = item.sy - self._height / 2
            radius = math.hypot(dx, dy)
            max_radius = 0.5 * min(self._width, self._height)
            color = _sample_gradient(self.gradient, clamp01(radius / max_radius))
        elif palette == "gradient_linear":
            t = clamp01((item.sx - self._width * 0.25) / max(1.0, self._width * 0.5))
            color = _sample_gradient(self.gradient, t)
        elif palette == "by_lat":
            theta, _ = _spherical_from_cartesian(item.world.x, item.world.y, item.world.z)
            factor = (1 - theta / math.pi) * 2 - 1
            color = self._hsl_from_params(factor, now_ms)
        elif palette == "by_lon":
            _, phi = _spherical_from_cartesian(item.world.x, item.world.y, item.world.z)
            factor = (phi / (2 * math.pi)) * 2 - 1
            color = self._hsl_from_params(factor, now_ms)
        elif palette == "by_noise":
            ap = appearance
            scale = max(0.05, float(ap.get("noiseScale", 1.0) or 1.0))
            speed = float(ap.get("noiseSpeed", 0.0) or 0.0)
            n = _value_noise3(
                item.world.x * scale + speed * now_ms * 0.001,
                item.world.y * scale,
                item.world.z * scale,
            )
            color = _sample_gradient(self.gradient, n)
        else:
            color = appearance.get("color", "#00C8FF")
        qcolor = QtGui.QColor(color)
        if not qcolor.isValid():
            qcolor = QtGui.QColor("#00C8FF")
        return qcolor

    def _hsl_from_params(self, factor: float, now_ms: float) -> str:
        ap = self.state.get("appearance", {})
        base = float(ap.get("h0", 0.0) or 0.0)
        delta = float(ap.get("dh", 0.0) or 0.0)
        wave = float(ap.get("wh", 0.0) or 0.0)
        hue = (base + delta * factor + wave * math.sin(now_ms * 0.001)) % 360
        sat = clamp01(0.55 + 0.2 * factor)
        light = clamp01(0.55 + 0.25 * factor)
        r, g, b = _hsl_to_rgb(hue / 360.0, sat, light)
        return _rgb_to_hex(r, g, b)

    # ---------------------------------------------------------------- main update
    def step(self, width: int, height: int) -> List[RenderItem]:
        if width <= 0 or height <= 0:
            return []
        now = self.now_ms
        dt = min(0.1, max(0.0, (now - self._last_ms) / 1000.0))
        self._last_ms = now
        cam = self.state.get("camera", {})
        omega = float(cam.get("omegaDegPerSec", 0.0) or 0.0)
        self._cam_theta_deg = (self._cam_theta_deg + omega * dt) % 360

        cam_theta = to_rad(self._cam_theta_deg)
        cam_height = to_rad(float(cam.get("camHeightDeg", 0.0) or 0.0))
        cam_tilt = to_rad(float(cam.get("camTiltDeg", 0.0) or 0.0))
        cam_radius = float(cam.get("camRadius", 3.2) or 3.2)
        fov = float(cam.get("fov", 600) or 600)
        fov = clamp(float(fov), 1.0, 5000.0)

        cos_theta = math.cos(cam_theta)
        sin_theta = math.sin(cam_theta)
        cos_height = math.cos(cam_height)
        sin_height = math.sin(cam_height)
        cos_tilt = math.cos(cam_tilt)
        sin_tilt = math.sin(cam_tilt)

        scale = 0.45 * min(width, height)
        focal = scale * (600.0 / fov)
        cx = width / 2
        cy = height / 2

        dyn = self.state.get("dynamics", {})
        pulse_amp = float(dyn.get("pulseA", 0.0) or 0.0)
        pulse_w = float(dyn.get("pulseW", 0.0) or 0.0)
        pulse_phi = to_rad(float(dyn.get("pulsePhaseDeg", 0.0) or 0.0))
        rot_phase_amp = to_rad(float(dyn.get("rotPhaseDeg", 0.0) or 0.0))

        items: List[RenderItem] = []
        screen_grid: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
        dist = self.state.get("distribution", {})
        dmin_px = float(dist.get("dmin_px", 0.0) or 0.0)
        cell = max(1.0, dmin_px) if dmin_px > 0 else 1.0
        if not self.base_points:
            return []

        for idx, base in enumerate(self.base_points):
            mod = self._apply_point_modifiers(base, idx, now)
            if not self._keep_point(mod, idx, now):
                continue
            phase = self._compute_phase_factor(mod, idx)
            pulse = 1 + pulse_amp * math.sin(pulse_w * now * 0.001 + pulse_phi + 2 * math.pi * phase)

            ang_x = to_rad(float(dyn.get("rotX", 0.0) or 0.0)) * (now * 0.001) + rot_phase_amp * phase
            ang_y = to_rad(float(dyn.get("rotY", 0.0) or 0.0)) * (now * 0.001) + rot_phase_amp * phase
            ang_z = to_rad(float(dyn.get("rotZ", 0.0) or 0.0)) * (now * 0.001) + rot_phase_amp * phase

            cos_x, sin_x = math.cos(ang_x), math.sin(ang_x)
            cos_y, sin_y = math.cos(ang_y), math.sin(ang_y)
            cos_z, sin_z = math.cos(ang_z), math.sin(ang_z)

            x = mod.x * pulse
            y = mod.y * pulse
            z = mod.z * pulse

            Xz = cos_z * x - sin_z * y
            Yz = sin_z * x + cos_z * y
            Zz = z

            Xx = Xz
            Yx = cos_x * Yz - sin_x * Zz
            Zx = sin_x * Yz + cos_x * Zz

            X = cos_y * Xx + sin_y * Zx
            Z = -sin_y * Xx + cos_y * Zx
            Y = Yx

            # camera transformation
            Xc = cos_theta * X - sin_theta * Z
            Zc = sin_theta * X + cos_theta * Z
            Yc = Y

            Yc2 = cos_height * Yc - sin_height * Zc
            Zc2 = sin_height * Yc + cos_height * Zc

            Xc3 = cos_tilt * Xc - sin_tilt * Yc2
            Yc3 = sin_tilt * Xc + cos_tilt * Yc2
            Zc3 = Zc2

            Zc3 += cam_radius
            if Zc3 <= 0.01:
                continue
            inv = focal / Zc3
            sx = cx + Xc3 * inv
            sy = cy + Yc3 * inv
            if not (math.isfinite(sx) and math.isfinite(sy)):
                continue

            if dmin_px > 0:
                ix = int(math.floor(sx / cell))
                iy = int(math.floor(sy / cell))
                keep = True
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        bucket = screen_grid.get((ix + dx, iy + dy))
                        if not bucket:
                            continue
                        for px, py in bucket:
                            if (sx - px) ** 2 + (sy - py) ** 2 < dmin_px ** 2:
                                keep = False
                                break
                        if not keep:
                            break
                    if not keep:
                        break
                if not keep:
                    continue
                screen_grid.setdefault((ix, iy), []).append((sx, sy))

            px_size = float(self.state.get("appearance", {}).get("px", 2.0) or 2.0)
            radius = max(1.0, px_size)

            item = RenderItem(
                sx=sx,
                sy=sy,
                r=radius,
                color=QtGui.QColor("#00C8FF"),
                alpha=1.0,
                depth=Zc3,
                world=Point3D(X, Y, Z, idx),
            )
            items.append(item)

        self._width = width
        self._height = height

        appearance = self.state.get("appearance", {})
        opacity = float(appearance.get("opacity", 1.0) or 1.0)
        alpha_depth = float(appearance.get("alphaDepth", 0.0) or 0.0)

        for item in items:
            item.color = self._pick_color(item, now)
            if alpha_depth > 0:
                t = clamp01(math.atan(max(0.0, item.depth)) / (math.pi / 2))
                depth_alpha = (1 - alpha_depth) + alpha_depth * (1 - t)
            else:
                depth_alpha = 1.0
            item.alpha = clamp01(opacity * depth_alpha * self._mask_weight(item.world, now))

        if self.state.get("system", {}).get("depthSort", True):
            items.sort(key=lambda it: it.depth, reverse=True)
        count = len(items)
        if count == 0:
            note = "step produced 0 items"
            visible = 0
            bounds = "none"
            avg_alpha = "0.000"
        else:
            note = ""
            visible = sum(1 for it in items if it.alpha > 0.001)
            min_x = min(it.sx for it in items)
            max_x = max(it.sx for it in items)
            min_y = min(it.sy for it in items)
            max_y = max(it.sy for it in items)
            bounds = f"x=[{min_x:.1f},{max_x:.1f}] y=[{min_y:.1f},{max_y:.1f}]"
            avg_alpha = f"{(sum(it.alpha for it in items) / count):.3f}"
        if (
            count != self._last_item_count
            or note != self._last_step_note
            or visible != self._last_visible_count
            or avg_alpha != self._last_avg_alpha
            or bounds != self._last_bounds
        ):
            self._debug(
                "step rendered %d items (%d visible) from %d base points (width=%d height=%d cam_radius=%.3f fov=%.1f avg_alpha=%s screen=%s)"
                % (
                    count,
                    visible,
                    len(self.base_points),
                    width,
                    height,
                    cam_radius,
                    fov,
                    avg_alpha,
                    bounds,
                )
            )
            if count == 0:
                self._debug(
                    "\tstate snapshot: distribution=%s appearance.opacity=%s"
                    % (
                        dict(self.state.get("distribution", {})),
                        self.state.get("appearance", {}).get("opacity", 1.0),
                    )
                )
            self._last_item_count = count
            self._last_step_note = note
            self._last_visible_count = visible
            self._last_avg_alpha = avg_alpha
            self._last_bounds = bounds
        return items


class _ViewWidgetBase:
    """Common behaviour shared by both the OpenGL and raster backends."""

    def _init_view_widget(self) -> None:
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, False)
        self.setAutoFillBackground(False)
        self.engine = DyxtenEngine()
        self._shape = "circle"
        self._transparent = True
        self._timer = QtCore.QTimer(self)
        self._frame_interval_ms = 16
        self._timer.timeout.connect(self.update)
        self._timer.start(self._frame_interval_ms)

    def _apply_frame_interval(self, interval_ms: int) -> None:
        """Update the refresh interval used by the render timer."""

        interval_ms = max(int(interval_ms), 0)
        if interval_ms == self._frame_interval_ms and self._timer.isActive() == (
            interval_ms > 0
        ):
            return
        self._frame_interval_ms = interval_ms
        if interval_ms <= 0:
            if self._timer.isActive():
                self._timer.stop()
            return
        if self._timer.isActive():
            self._timer.setInterval(interval_ms)
        else:
            self._timer.start(interval_ms)

    # ------------------------------------------------------------------ OpenGL hooks
    def initializeGL(self) -> None:  # pragma: no cover - requires GUI context
        self._gl = QtGui.QOpenGLFunctions()
        self._gl.initializeOpenGLFunctions()
        self._apply_clear_color()

    def resizeGL(self, width: int, height: int) -> None:  # pragma: no cover - requires GUI context
        # No custom viewport management required but keep method for completeness
        del width, height

    def _apply_clear_color(self) -> None:
        if self._gl is None:
            return
        alpha = 0.0 if self._transparent else 1.0
        self._gl.glClearColor(0.0, 0.0, 0.0, alpha)

    # ------------------------------------------------------------------ API
    def set_params(self, payload: Mapping[str, object]) -> None:
        previous_shape = self._shape
        self.engine.set_params(payload)
        appearance = self.engine.state.get("appearance", {})
        self._shape = appearance.get("shape", "circle")
        system = self.engine.state.get("system", {})
        transparent_flag = system.get("transparent")
        if transparent_flag is None:
            transparent = True
        else:
            transparent = bool(transparent_flag)
        frame_interval = system.get("frameIntervalMs")
        if frame_interval is None:
            target_interval = 16
        else:
            try:
                target_interval = int(float(frame_interval))
            except (TypeError, ValueError):
                target_interval = 16
        self._apply_frame_interval(target_interval)
        if transparent != self._transparent:
            self.set_transparent(transparent)
        if previous_shape != self._shape:
            self.update()

    def current_donut(self) -> dict:
        return self.engine.state.get("donut", default_donut_config())

    def set_transparent(self, enabled: bool) -> None:  # pragma: no cover - simple setter
        self._transparent = bool(enabled)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, enabled)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, enabled)
        self.setAutoFillBackground(not enabled)
        self._apply_clear_color()
        self.update()

    # ------------------------------------------------------------------ Rendering helpers
    def _render_with_painter(self, painter: QtGui.QPainter) -> None:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        if self._transparent:
            painter.setBackgroundMode(QtCore.Qt.TransparentMode)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
            painter.fillRect(self.rect(), QtCore.Qt.transparent)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        else:
            painter.fillRect(self.rect(), QtGui.QColor("black"))
        width = max(1, self.width())
        height = max(1, self.height())
        items = self.engine.step(width, height)
        blend_mode = (
            self.engine.state.get("appearance", {}).get("blendMode", "source-over")
        )
        painter.setCompositionMode(_map_blend_mode(blend_mode))
        for item in items:
            color = QtGui.QColor(item.color)
            color.setAlphaF(clamp01(item.alpha))
            painter.setBrush(color)
            painter.setPen(QtCore.Qt.NoPen)
            if self._shape == "square":
                painter.drawRect(QtCore.QRectF(item.sx - item.r, item.sy - item.r, item.r * 2, item.r * 2))
            else:
                painter.drawEllipse(QtCore.QRectF(item.sx - item.r, item.sy - item.r, item.r * 2, item.r * 2))

        # Draw permanent concentric marker circles centred on the viewport
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        painter.setBrush(QtCore.Qt.NoBrush)

        center_x = width / 2.0
        center_y = height / 2.0
        if width > 0 and height > 0:
            base_area = (width * height) / 3.0
            base_radius = math.sqrt(max(base_area, 0.0) / math.pi)

            def _draw_marker_circle(color: QtGui.QColor, radius: float) -> None:
                diameter = radius * 2.0
                painter.setPen(QtGui.QPen(color, 2.0))
                painter.drawEllipse(QtCore.QRectF(center_x - radius, center_y - radius, diameter, diameter))

            radius_red = base_radius * 0.5
            radius_yellow = radius_red * 1.15
            radius_blue = radius_yellow * 1.10
            _draw_marker_circle(QtGui.QColor("red"), radius_red)
            _draw_marker_circle(QtGui.QColor("yellow"), radius_yellow)
            _draw_marker_circle(QtGui.QColor("blue"), radius_blue)


class _OpenGLViewWidget(QtWidgets.QOpenGLWidget, _ViewWidgetBase):
    """OpenGL-backed renderer when the system can create a GL context."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        QtWidgets.QOpenGLWidget.__init__(self, parent)
        self._gl: Optional[QtGui.QOpenGLFunctions] = None
        self._init_view_widget()

    def initializeGL(self) -> None:  # pragma: no cover - requires GUI context
        try:
            self._gl = QtGui.QOpenGLFunctions()
            self._gl.initializeOpenGLFunctions()
        except Exception as exc:  # pragma: no cover - defensive
            self._gl = None
            print(
                f"[Dyxten][WARN] OpenGL initialisation failed: {exc}. Falling back to raster clear handling.",
                file=sys.stderr,
            )
        self._apply_clear_color()

    def resizeGL(self, width: int, height: int) -> None:  # pragma: no cover - requires GUI context
        # No custom viewport management required but keep method for completeness
        del width, height

    def _apply_clear_color(self) -> None:
        if self._gl is None:
            return
        alpha = 0.0 if self._transparent else 1.0
        self._gl.glClearColor(0.0, 0.0, 0.0, alpha)

    def set_transparent(self, enabled: bool) -> None:  # pragma: no cover - trivial wrapper
        super().set_transparent(enabled)
        self._apply_clear_color()

    def paintGL(self) -> None:  # pragma: no cover - requires GUI context
        if self._gl is not None:
            try:
                # GL_COLOR_BUFFER_BIT constant
                self._gl.glClear(0x00004000)
            except Exception:
                pass
        painter = QtGui.QPainter(self)
        try:
            self._render_with_painter(painter)
        finally:
            painter.end()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.update()


class _RasterViewWidget(QtWidgets.QWidget, _ViewWidgetBase):
    """Fallback renderer using the traditional raster ``QWidget`` backend."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        QtWidgets.QWidget.__init__(self, parent)
        self._init_view_widget()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        del event
        painter = QtGui.QPainter(self)
        try:
            self._render_with_painter(painter)
        finally:
            painter.end()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.update()


def _should_use_opengl(force_backend: Optional[str]) -> bool:
    if force_backend == "raster":
        return False
    if force_backend == "opengl":
        return True
    if os.environ.get("DYXTEN_FORCE_RASTER", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return hasattr(QtWidgets, "QOpenGLWidget")


def DyxtenViewWidget(
    parent: Optional[QtWidgets.QWidget] = None,
    *,
    force_backend: Optional[str] = None,
) -> QtWidgets.QWidget:
    """Factory returning the best available renderer widget.

    Parameters
    ----------
    parent:
        Parent widget used by Qt for ownership.
    force_backend:
        Optional string controlling the backend selection.  ``"opengl"`` forces the
        OpenGL widget while ``"raster"`` selects the pure QWidget implementation.

    Returns
    -------
    QtWidgets.QWidget
        A widget exposing the same public API regardless of the backend choice.
    """

    if _should_use_opengl(force_backend):
        try:
            widget = _OpenGLViewWidget(parent)
            setattr(widget, "backend_name", "opengl")
            setattr(widget, "uses_opengl", True)
            return widget
        except Exception as exc:
            print(
                f"[Dyxten][WARN] Unable to initialise OpenGL backend ({exc!r}). Using raster widget instead.",
                file=sys.stderr,
            )
    widget = _RasterViewWidget(parent)
    setattr(widget, "backend_name", "raster")
    setattr(widget, "uses_opengl", False)
    return widget




















































def _sample_implicit_surface(
    count: int,
    radius: float,
    func,
    iso: float,
    thickness: float,
) -> List[Point3D]:
    out: List[Point3D] = []
    attempts = 0
    max_attempts = max(1000, count * 50)
    while len(out) < count and attempts < max_attempts:
        attempts += 1
        x = random.uniform(-radius, radius)
        y = random.uniform(-radius, radius)
        z = random.uniform(-radius, radius)
        value = func(x, y, z)
        if abs(value - iso) <= thickness:
            out.append(Point3D(x, y, z))
    return out






    def sphere(r: float) -> float:
        return math.sqrt(x * x + y * y + z * z) - r

    def box(sx: float, sy: float, sz: float) -> float:
        dx = abs(x) - sx
        dy = abs(y) - sy
        dz = abs(z) - sz
        outside = math.sqrt(max(dx, 0.0) ** 2 + max(dy, 0.0) ** 2 + max(dz, 0.0) ** 2)
        inside = min(max(dx, max(dy, dz)), 0.0)
        return outside + inside

    def torus(R: float, r: float) -> float:
        q = math.sqrt(x * x + z * z) - R
        return math.sqrt(q * q + y * y) - r

    env = {
        "sphere": sphere,
        "box": box,
        "torus": torus,
        "union": lambda a, b: min(a, b),
        "inter": lambda a, b: max(a, b),
        "sub": lambda a, b: max(a, -b),
        "abs": abs,
        "min": min,
        "max": max,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
    }
    try:
        return float(eval(expr, {"__builtins__": {}}, env))
    except Exception:
        return 0.0




DyxtenEngine._GEOMETRY_GENERATORS = {}


def _wrap_point_list(raw_points, cap):
    points: List[Point3D] = []
    for item in raw_points:
        if isinstance(item, Point3D):
            points.append(item.copy())
        elif isinstance(item, (tuple, list)) and len(item) >= 3:
            try:
                points.append(Point3D(float(item[0]), float(item[1]), float(item[2])))
            except (TypeError, ValueError):
                continue
    if cap and cap > 0:
        return points[:cap]
    return points


def _wrap_builtin_generator(generator: GeometryGenerator) -> GeometryGenerator:
    def _adapter(geo: Mapping[str, object], cap: int) -> List[Point3D]:
        raw_points = generator(geo, cap)
        return _wrap_point_list(raw_points, cap)

    return _adapter


_JSON_TOPOLOGY_LIBRARY = get_topology_library()
_json_generators = _JSON_TOPOLOGY_LIBRARY.generators()
for name, generator in _json_generators.items():
    definition = _JSON_TOPOLOGY_LIBRARY.get(name)
    if definition is None:
        continue

    def _wrap(gen: GeometryGenerator, *, defaults: Mapping[str, object]):
        def _adapter(geo: Mapping[str, object], cap: int) -> List[Point3D]:
            params: Dict[str, object] = dict(defaults)
            extra = {k: v for k, v in geo.items() if isinstance(k, str) and k not in {"code", "topology"}}
            params.update(extra)
            def _as_positive_int(value: object) -> int:
                try:
                    number = int(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    return 0
                return number if number > 0 else 0

            requested = _as_positive_int(params.get("N"))
            default_n = _as_positive_int(defaults.get("N"))
            cap_n = _as_positive_int(cap)
            target = requested or default_n or cap_n or 4096
            if cap_n:
                target = min(target, cap_n)
            params["N"] = target
            raw_points = gen(params, target)
            return _wrap_point_list(raw_points, target)

        return _adapter

    DyxtenEngine._GEOMETRY_GENERATORS[name] = _wrap(generator, defaults=definition.defaults)

for name, generator in BUILTIN_GENERATORS.items():
    if name not in DyxtenEngine._GEOMETRY_GENERATORS:
        DyxtenEngine._GEOMETRY_GENERATORS[name] = _wrap_builtin_generator(generator)


