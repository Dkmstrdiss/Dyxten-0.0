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
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Mapping, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from ..donut_hub import DEFAULT_DONUT_BUTTON_COUNT, default_donut_config, sanitize_donut_state
from ..orbital_utils import solve_tangent_radii

try:
    from ..topology_registry import get_topology_library
except ImportError:  # pragma: no cover - compat exécution directe
    from core.topology_registry import get_topology_library  # type: ignore


GeometryGenerator = Callable[[Mapping[str, object], int], List["Point3D"]]

__all__ = ["DyxtenViewWidget"]

# ---------------------------------------------------------------------------
# Data structures


@dataclass
class Point3D:
    """Simple structure storing a 3D point and the seed used to generate it."""

    x: float
    y: float
    z: float
    seed: int = 0

    def copy(self) -> "Point3D":
        return Point3D(self.x, self.y, self.z, self.seed)


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
    gravity_weight: float = 0.0
    role: str = "cloud"


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def to_rad(deg: float) -> float:
    return deg * math.pi / 180.0


def _coerce_float(value: object, default: float = 0.0) -> float:
    """Return ``value`` converted to ``float`` when possible."""

    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


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
# OpenGL helpers


def _create_opengl_functions() -> Tuple[Optional[object], Optional[BaseException]]:
    """Safely instantiate ``QOpenGLFunctions`` when available.

    Returns a tuple ``(functions, error)`` where ``functions`` is the
    initialised OpenGL function table or ``None`` when the binding is not
    present.  ``error`` contains the exception encountered while creating or
    initialising the functions so that callers can surface a meaningful
    diagnostic message.
    """

    factory = getattr(QtGui, "QOpenGLFunctions", None)
    if factory is None:
        return None, AttributeError("PyQt5.QtGui has no attribute 'QOpenGLFunctions'")
    try:
        functions = factory()
    except Exception as exc:  # pragma: no cover - depends on bindings
        return None, exc
    try:
        functions.initializeOpenGLFunctions()
    except Exception as exc:  # pragma: no cover - depends on runtime GL state
        return None, exc
    return functions, None


# ---------------------------------------------------------------------------
# Utility helpers translated from the JavaScript implementation


def _rand_for_index(index: int, salt: int = 0) -> float:
    s = index * 12.9898 + salt * 78.233
    x = math.sin(s) * 43758.5453
    return x - math.floor(x)


def _value_noise3(x: float, y: float, z: float) -> float:
    xi = math.floor(x)
    yi = math.floor(y)
    zi = math.floor(z)
    xf = x - xi
    yf = y - yi
    zf = z - zi

    def _hash(ix: int, iy: int, iz: int) -> float:
        n = ix * 15731 + iy * 789221 + iz * 1376312589
        n = (n << 13) ^ n
        return (1.0 - ((n * (n * n * 15731 + 789221) + 1376312589) & 0x7FFFFFFF) / 1073741824.0) * 0.5 + 0.5

    def _lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    def _smooth(t: float) -> float:
        return t * t * (3.0 - 2.0 * t)

    c000 = _hash(xi, yi, zi)
    c100 = _hash(xi + 1, yi, zi)
    c010 = _hash(xi, yi + 1, zi)
    c110 = _hash(xi + 1, yi + 1, zi)
    c001 = _hash(xi, yi, zi + 1)
    c101 = _hash(xi + 1, yi, zi + 1)
    c011 = _hash(xi, yi + 1, zi + 1)
    c111 = _hash(xi + 1, yi + 1, zi + 1)

    u = _smooth(xf)
    v = _smooth(yf)
    w = _smooth(zf)

    x00 = _lerp(c000, c100, u)
    x10 = _lerp(c010, c110, u)
    x01 = _lerp(c001, c101, u)
    x11 = _lerp(c011, c111, u)
    y0 = _lerp(x00, x10, v)
    y1 = _lerp(x01, x11, v)
    return _lerp(y0, y1, w)


def _gen_uv_sphere(geo: Mapping[str, object], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    lat_steps = max(2, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    points: List[Point3D] = []
    for i in range(lat_steps):
        v = i / (lat_steps - 1 if lat_steps > 1 else 1)
        theta = v * math.pi
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        for j in range(lon_steps):
            u = j / lon_steps
            phi = u * 2.0 * math.pi
            cos_phi = math.cos(phi)
            sin_phi = math.sin(phi)
            points.append(
                Point3D(
                    radius * sin_theta * cos_phi,
                    radius * cos_theta,
                    radius * sin_theta * sin_phi,
                )
            )
    if cap and cap > 0:
        return points[:cap]
    return points


_DEFAULT_GENERATORS: Dict[str, GeometryGenerator] = {
    "uv_sphere": _gen_uv_sphere,
}


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
            "markerCircles": {"red": 0.16, "yellow": 0.19, "blue": 0.22},
            "donutButtonSize": 100,
            "donutRadiusRatio": 0.35,
        },
        "indicator": {
            "centerLines": {
                "all": False,
                "buttons": {str(idx + 1): False for idx in range(DEFAULT_DONUT_BUTTON_COUNT)},
            },
            "yellowCircleRatio": 0.19,
            "orbitalZones": {
                "enabled": True,
                "diameters": [120.0 for _ in range(DEFAULT_DONUT_BUTTON_COUNT)],
            },
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
        self._marker_radii: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._donut_layout: List[Tuple[float, float, float]] = []
        # Empreintes persistantes déposées par les particules lorsqu'elles
        # franchissent le bord du cercle rouge. Chaque entrée :
        # (x, y, QColor, rayon, timestamp_ms, identifiant)
        self._imprints: List[Tuple[float, float, QtGui.QColor, float, float, int]] = []
        self._imprint_counter = 0
        # Positions précédentes des particules pour détecter un passage du bord
        # clé = seed (index de particule), valeur = (sx, sy, dist_center)
        self._last_particle_positions: Dict[int, Tuple[float, float, float]] = {}
        # Historique des trajectoires des particules (pour trajectoire initiale)
        self._particle_traces: Dict[int, Deque[Tuple[float, float]]] = {}
        self._trail_max_points = 90
        # Limite de sécurité pour éviter une croissance mémoire illimitée.
        self._max_imprints = 5000
        # Particules orbitales déclenchées par chaque empreinte
        self._orbiters: List[Dict[str, object]] = []
        # Positions calculées pour affichage à la dernière frame: (sx, sy, QColor, r, alpha)
        self._orbiters_draw: List[Tuple[float, float, QtGui.QColor, float, float]] = []
        self._max_orbiters = 512
        self._mod_noise_warp = 0.0
        self._mod_field_flow = 0.0
        self._mod_repel_force = 0.0
        self._mod_density_pulse = 0.0
        self._mod_orient_x = 0.0
        self._mod_orient_y = 0.0
        self._mod_orient_z = 0.0
        self._modifiers_active = False
        self._update_modifier_flags()
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
                self._donut_layout = []
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
        self._update_modifier_flags()

    def _update_modifier_flags(self) -> None:
        dist = self.state.get("distribution", {})
        if not isinstance(dist, Mapping):
            dist = {}
        dyn = self.state.get("dynamics", {})
        if not isinstance(dyn, Mapping):
            dyn = {}

        def _orient_value(key: str) -> float:
            raw = dyn.get(key)
            if raw is None:
                raw = dist.get(key)
            return _coerce_float(raw, 0.0)

        self._mod_noise_warp = _coerce_float(dist.get("noiseWarp"), 0.0)
        self._mod_field_flow = _coerce_float(dist.get("fieldFlow"), 0.0)
        self._mod_repel_force = _coerce_float(dist.get("repelForce"), 0.0)
        self._mod_density_pulse = _coerce_float(dist.get("densityPulse"), 0.0)
        self._mod_orient_x = _orient_value("orientXDeg")
        self._mod_orient_y = _orient_value("orientYDeg")
        self._mod_orient_z = _orient_value("orientZDeg")

        self._modifiers_active = any(
            abs(value) > 1e-6
            for value in (
                self._mod_noise_warp,
                self._mod_field_flow,
                self._mod_repel_force,
                self._mod_density_pulse,
                self._mod_orient_x,
                self._mod_orient_y,
                self._mod_orient_z,
            )
        )

    def _remove_imprint_by_id(self, imprint_id: Optional[int]) -> None:
        if imprint_id is None:
            return
        self._imprints = [entry for entry in self._imprints if entry[5] != imprint_id]

    def reset_visual_state(self) -> None:
        """Clear transient visual elements while preserving configuration."""

        self._imprints.clear()
        self._imprint_counter = 0
        self._orbiters.clear()
        self._orbiters_draw.clear()
        self._last_particle_positions.clear()
        self._particle_traces.clear()
        self._start_time = time.perf_counter()
        self._last_ms = 0.0
        self.rebuild_geometry()

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
        if not isinstance(system, Mapping):
            system = {}
        orbit_cfg = self.state.get("orbit", {})
        if not isinstance(orbit_cfg, Mapping):
            orbit_cfg = {}

        def _orbit_value(key: str, fallback: object) -> object:
            if key in orbit_cfg:
                return orbit_cfg.get(key, fallback)
            return system.get(key, fallback)
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
        self._particle_traces.clear()
        self._last_particle_positions.clear()
        count = len(centered)
        if count != self._last_base_count:
            self._debug(
                "rebuild_geometry generated %d points (topology=%s, cap=%s, dmin=%s)"
                % (count, topology, cap or "none", dmin)
            )
            self._last_base_count = count

    # ---------------------------------------------------------------- animation helpers
    def _apply_point_modifiers(self, base: Point3D, seed: int, now_ms: float) -> Point3D:
        if not self._modifiers_active:
            return base

        g = self.state.get("geometry", {})
        R = float(g.get("R", 1.0) or 1.0)
        x, y, z = base.x, base.y, base.z

        noise_warp = self._mod_noise_warp
        if noise_warp:
            amp = noise_warp * R * 0.4
            freq = 1.3
            anim = now_ms * 0.0006
            x += amp * (_value_noise3((base.x + anim) * freq, (base.y - anim) * freq, (base.z + 2 + anim) * freq) * 2 - 1)
            y += amp * (_value_noise3((base.x - anim) * freq, (base.y + anim) * freq, (base.z - anim) * freq) * 2 - 1)
            z += amp * (_value_noise3((base.x + anim * 0.5) * freq, (base.y + 2 * anim) * freq, (base.z - anim * 0.25) * freq) * 2 - 1)

        flow = self._mod_field_flow
        if flow:
            angle = (flow * 0.4 * now_ms * 0.001) + (flow * 0.3 * (y / max(1e-6, R)))
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            x, z = cos_a * x - sin_a * z, sin_a * x + cos_a * z

        repel = self._mod_repel_force
        if repel:
            r = math.sqrt(x * x + y * y + z * z) or 1.0
            diff = R - r
            k = repel * 0.6
            x += diff * k * (x / r)
            y += diff * k * (y / r)
            z += diff * k * (z / r)

        pulse = self._mod_density_pulse
        if pulse:
            scale = 1 + 0.3 * pulse * math.sin(now_ms * 0.001 * 2 * math.pi)
            x *= scale
            y *= scale
            z *= scale

        orient_x = self._mod_orient_x
        orient_y = self._mod_orient_y
        orient_z = self._mod_orient_z

        if orient_x:
            ox = to_rad(orient_x)
            cos_x, sin_x = math.cos(ox), math.sin(ox)
            y, z = cos_x * y - sin_x * z, sin_x * y + cos_x * z
        if orient_y:
            oy = to_rad(orient_y)
            cos_y, sin_y = math.cos(oy), math.sin(oy)
            x, z = cos_y * x + sin_y * z, -sin_y * x + cos_y * z
        if orient_z:
            oz = to_rad(orient_z)
            cos_z, sin_z = math.cos(oz), math.sin(oz)
            x, y = cos_z * x - sin_z * y, sin_z * x + cos_z * y

        return Point3D(x, y, z, seed)

    def _keep_point(self, point: Point3D, seed: int, now_ms: float) -> bool:
        del now_ms
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

        weight = clamp01(weight)
        if weight <= 0:
            return False
        if weight >= 1:
            return True
        return _rand_for_index(seed + 1) <= weight

    def update_donut_layout(
        self,
        width: int,
        height: int,
        centers: Sequence[Tuple[float, float]],
        radii: Optional[Sequence[float]] = None,
    ) -> None:
        """Store the button centres provided by the overlay layer."""

        if width <= 0 or height <= 0:
            self._donut_layout = []
            return

        center_list = list(centers)
        if not center_list:
            self._donut_layout = []
            return

        radius_list: List[Optional[float]] = []
        if radii is not None:
            radius_list = [float(r) if isinstance(r, (int, float)) else None for r in radii]

        w = float(width)
        h = float(height)
        normalized: List[Tuple[float, float, float]] = []
        for idx, (sx, sy) in enumerate(center_list):
            if not isinstance(sx, (int, float)) or not isinstance(sy, (int, float)):
                continue
            if not (math.isfinite(sx) and math.isfinite(sy)):
                continue
            clamped_x = clamp(float(sx), 0.0, w)
            clamped_y = clamp(float(sy), 0.0, h)
            radius_px = 0.0
            if idx < len(radius_list):
                candidate = radius_list[idx]
                if candidate is not None and math.isfinite(candidate):
                    radius_px = max(0.0, float(candidate))
            normalized.append((clamped_x / w, clamped_y / h, radius_px))

        self._donut_layout = normalized

    def _compute_donut_orbits(
        self, width: int, height: int
    ) -> Tuple[List[Tuple[float, float]], List[float], float]:
        if self._donut_layout and width > 0 and height > 0:
            centers: List[Tuple[float, float]] = []
            radii: List[float] = []
            for cx_norm, cy_norm, radius_px in self._donut_layout:
                px = clamp01(cx_norm) * width
                py = clamp01(cy_norm) * height
                centers.append((px, py))
                if math.isfinite(radius_px) and radius_px > 0.0:
                    radii.append(float(radius_px))
                else:
                    radii.append(0.0)

            cx = width / 2.0
            cy = height / 2.0
            fallback_radius = max(12.0, min(width, height) * 0.05)
            if centers:
                radii_to_center = [math.hypot(x - cx, y - cy) for x, y in centers]
                avg_radius = sum(radii_to_center) / len(radii_to_center) if radii_to_center else 0.0
                if avg_radius > 0.0 and len(centers) > 0:
                    spacing = (2.0 * math.pi * avg_radius) / len(centers)
                    fallback_radius = clamp(spacing * 0.25, 10.0, max(18.0, spacing * 0.65))

            positive_button = [r for r in radii if r > 0.0]
            if positive_button:
                average_button = sum(positive_button) / len(positive_button)
                fallback_radius = max(average_button, fallback_radius)

            return centers, radii, fallback_radius

        donut = self.state.get("donut", {})
        if not isinstance(donut, Mapping):
            donut = default_donut_config()
        buttons = donut.get("buttons")
        if not isinstance(buttons, Sequence) or not buttons:
            buttons = default_donut_config()["buttons"]
        count = max(1, min(len(buttons), DEFAULT_DONUT_BUTTON_COUNT))
        ratio_raw = donut.get("radiusRatio", 0.35)
        try:
            ratio = float(ratio_raw)
        except (TypeError, ValueError):
            ratio = 0.35
        ratio = clamp(ratio, 0.05, 0.9)
        radius = min(width, height) * ratio
        cx = width / 2.0
        cy = height / 2.0
        centers: List[Tuple[float, float]] = []
        for index in range(count):
            angle = (index / count) * 2.0 * math.pi - math.pi / 2.0
            centers.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
        if radius <= 0 or count <= 0:
            fallback_radius = max(12.0, min(width, height) * 0.05)
        else:
            spacing = (2.0 * math.pi * radius) / count
            fallback_radius = clamp(spacing * 0.25, 10.0, max(18.0, spacing * 0.65))
        radii = [fallback_radius for _ in range(len(centers))]
        return centers, radii, fallback_radius

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

    def marker_radii(self, width: int, height: int) -> Tuple[float, float, float]:
        del width, height
        return self._marker_radii

    def _compute_marker_radii(self, width: float, height: float) -> Tuple[float, float, float]:
        """Compute the radii of the red, yellow and blue marker circles.

        This is a copy of the helper used by the view widget but adapted to run
        on the engine so calls from :meth:`step` can compute radii without
        depending on the widget instance.
        """

        if width <= 0.0 or height <= 0.0:
            return 0.0, 0.0, 0.0
        min_dim = max(1.0, min(width, height))
        base_area = (width * height) / 3.0
        base_radius = math.sqrt(max(base_area, 0.0) / math.pi)
        radius_red = base_radius * 0.5
        radius_yellow = radius_red * 1.15
        radius_blue = radius_yellow * 1.10
        max_radius = min_dim / 2.0
        radius_red = min(radius_red, max_radius)
        radius_yellow = min(radius_yellow, max_radius)
        radius_blue = min(radius_blue, max_radius)

        system = self.state.get("system", {})
        indicator_cfg = self.state.get("indicator")
        yellow_override_ratio: Optional[float] = None
        if isinstance(indicator_cfg, Mapping):
            raw_yellow = indicator_cfg.get("yellowCircleRatio")
            try:
                yellow_override_ratio = float(raw_yellow)
            except (TypeError, ValueError):
                yellow_override_ratio = None
            if yellow_override_ratio is not None:
                yellow_override_ratio = clamp(yellow_override_ratio, 0.0, 0.5)

        marker_cfg = system.get("markerCircles")
        if isinstance(marker_cfg, Mapping):
            def _resolve(key: str, fallback: float) -> float:
                raw = marker_cfg.get(key, fallback / min_dim)
                try:
                    ratio = float(raw)
                except (TypeError, ValueError):
                    ratio = fallback / min_dim
                ratio = clamp(ratio, 0.0, 0.5)
                return ratio * min_dim

            radius_red = _resolve("red", radius_red)
            radius_yellow = _resolve("yellow", radius_yellow)
            # Blue circle now uses donutRadiusRatio directly
            donut_radius_ratio = system.get("donutRadiusRatio", 0.35)
            try:
                donut_radius_ratio = float(donut_radius_ratio)
            except (TypeError, ValueError):
                donut_radius_ratio = 0.35
            donut_radius_ratio = clamp(donut_radius_ratio, 0.05, 0.90)
            radius_blue = min_dim * donut_radius_ratio

        if yellow_override_ratio is not None:
            radius_yellow = yellow_override_ratio * min_dim

        return radius_red, radius_yellow, radius_blue

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
        system = self.state.get("system", {})

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

        radius_red, radius_yellow, radius_blue = self._compute_marker_radii(width, height)
        self._marker_radii = (radius_red, radius_yellow, radius_blue)

        dyn = self.state.get("dynamics", {})
        pulse_amp = float(dyn.get("pulseA", 0.0) or 0.0)
        pulse_w = float(dyn.get("pulseW", 0.0) or 0.0)
        pulse_phi = to_rad(float(dyn.get("pulsePhaseDeg", 0.0) or 0.0))
        rot_phase_amp = to_rad(float(dyn.get("rotPhaseDeg", 0.0) or 0.0))

        projected: List[Dict[str, object]] = []
        screen_grid: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
        dist = self.state.get("distribution", {})
        dmin_px = float(dist.get("dmin_px", 0.0) or 0.0)
        cell = max(1.0, dmin_px) if dmin_px > 0 else 1.0
        donut_centers, donut_radii, fallback_orbit_radius = self._compute_donut_orbits(width, height)
        donut_count = len(donut_centers)

        orbit_cfg = self.state.get("orbit", {})
        if not isinstance(orbit_cfg, Mapping):
            orbit_cfg = {}

        def _orbit_value(key: str, fallback: object) -> object:
            # Prefer an explicit orbit-specific override when present, otherwise
            # fall back to the system-level configuration.
            if key in orbit_cfg:
                return orbit_cfg.get(key, fallback)
            return system.get(key, fallback)

        def _safe_float_key(name: str, fallback: float) -> float:
            try:
                return float(_orbit_value(name, fallback))
            except (TypeError, ValueError):
                return fallback

        gravity_strength = clamp01(_safe_float_key("donutGravityStrength", 1.0))
        gravity_falloff = clamp(_safe_float_key("donutGravityFalloff", 1.0), 0.2, 5.0)
        ring_offset = clamp(_safe_float_key("donutGravityRingOffset", 12.0), 0.0, 150.0)
        orbit_speed_multiplier = clamp(_safe_float_key("orbitSpeed", 1.0), 0.0, 5.0)
        transition_duration_cfg = max(1.0, _safe_float_key("orbiterTransitionDuration", -1.0))
        if transition_duration_cfg <= 0.0:
            approach_duration_cfg = max(1.0, _safe_float_key("orbiterApproachDuration", 700.0))
            return_duration_cfg = max(1.0, _safe_float_key("orbiterReturnDuration", approach_duration_cfg))
        else:
            approach_duration_cfg = transition_duration_cfg
            return_duration_cfg = transition_duration_cfg
        required_turns_cfg = max(0.0, _safe_float_key("orbiterRequiredTurns", 1.0))
        max_orbit_ms_cfg = max(100.0, _safe_float_key("orbiterMaxOrbitMs", 4000.0))
        ease_in_power_cfg = clamp(
            _safe_float_key("orbiterTransitionEaseInPower", 3.0), 0.5, 8.0
        )
        ease_out_power_cfg = clamp(
            _safe_float_key("orbiterTransitionEaseOutPower", 3.0), 0.5, 8.0
        )
        transition_mode_cfg = str(_orbit_value("orbiterTransitionMode", "") or "")
        snap_mode_cfg = transition_mode_cfg or str(_orbit_value("orbiterSnapMode", "default") or "default")
        detach_mode_cfg = transition_mode_cfg or str(_orbit_value("orbiterDetachMode", snap_mode_cfg) or snap_mode_cfg)
        trajectory_mode_cfg = str(_orbit_value("orbiterTrajectory", "") or "")
        if trajectory_mode_cfg:
            approach_traj_cfg = trajectory_mode_cfg
            return_traj_cfg = trajectory_mode_cfg
        else:
            approach_traj_cfg = str(_orbit_value("orbiterApproachTrajectory", "line") or "line")
            return_traj_cfg = str(_orbit_value("orbiterReturnTrajectory", approach_traj_cfg) or approach_traj_cfg)
        trajectory_bend_cfg = clamp(_safe_float_key("orbiterTrajectoryBend", 0.35), -2.0, 2.0)
        trajectory_arc_direction_cfg = str(_orbit_value("orbiterTrajectoryArcDirection", "auto") or "auto")
        spiral_turns_cfg = clamp(_safe_float_key("orbiterSpiralTurns", 1.5), 0.1, 24.0)
        spiral_tightness_cfg = clamp(_safe_float_key("orbiterSpiralTightness", 0.35), -2.0, 2.0)
        wave_amplitude_cfg = clamp(_safe_float_key("orbiterWaveAmplitude", 0.3), 0.0, 5.0)
        wave_frequency_cfg = clamp(_safe_float_key("orbiterWaveFrequency", 3.0), 0.0, 20.0)
        trail_blend_cfg = clamp01(_safe_float_key("orbiterTrailBlend", 0.7))
        trail_smoothing_cfg = clamp01(_safe_float_key("orbiterTrailSmoothing", 0.4))
        trail_memory_seconds_cfg = clamp(_safe_float_key("orbiterTrailMemorySeconds", 2.0), 0.1, 12.0)
        desired_trail_points = max(8, min(600, int(trail_memory_seconds_cfg * 60.0)))
        if desired_trail_points != self._trail_max_points:
            self._trail_max_points = desired_trail_points
            for seed, trace in list(self._particle_traces.items()):
                self._particle_traces[seed] = deque(trace, maxlen=self._trail_max_points)
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

            world_point = Point3D(X, Y, Z, idx)

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
            dist_center = math.hypot(sx - cx, sy - cy)
            gravity_weight = 0.0
            orbit_descriptor: Optional[Dict[str, float]] = None
            if donut_count > 0 and radius_red > 0.0:
                outer_span = max(1.0, radius_blue - radius_red)
                outside = dist_center - radius_red
                if outside > 0.0:
                    progress = clamp01(outside / outer_span)
                    progress = clamp01(progress ** gravity_falloff)
                    pull = clamp01(progress * gravity_strength)
                    if pull > 0.0:
                        nearest_idx = 0
                        nearest_dist = float("inf")
                        for btn_idx, (center_x, center_y) in enumerate(donut_centers):
                            d = (sx - center_x) ** 2 + (sy - center_y) ** 2
                            if d < nearest_dist:
                                nearest_dist = d
                                nearest_idx = btn_idx
                        center_x, center_y = donut_centers[nearest_idx]
                        button_radius = 0.0
                        if nearest_idx < len(donut_radii):
                            button_radius = float(donut_radii[nearest_idx])
                        if not math.isfinite(button_radius) or button_radius <= 0.0:
                            button_radius = fallback_orbit_radius
                        phase_seed = _rand_for_index(idx, 311)
                        speed_seed = _rand_for_index(idx, 733)
                        base_speed = 0.6 + 1.2 * speed_seed
                        orbit_speed = orbit_speed_multiplier * base_speed
                        orbit_angle = phase_seed * 2 * math.pi + now * 0.001 * orbit_speed * 2 * math.pi
                        jitter = 1.0 + 0.2 * (_rand_for_index(idx, 911) - 0.5)
                        target_radius = max(1.0, button_radius + ring_offset)
                        orbit_radius = max(1.0, target_radius * jitter)
                        sx_orbit = center_x + math.cos(orbit_angle) * orbit_radius
                        sy_orbit = center_y + math.sin(orbit_angle) * orbit_radius
                        sx = sx + (sx_orbit - sx) * pull
                        sy = sy + (sy_orbit - sy) * pull
                        dist_center = math.hypot(sx - cx, sy - cy)
                        orbit_descriptor = {
                            "sx": sx_orbit,
                            "sy": sy_orbit,
                            "weight": pull,
                            "radius": radius,
                            "depth": Zc3,
                        }
                        gravity_weight = pull
            projected.append(
                {
                    "idx": idx,
                    "sx": sx,
                    "sy": sy,
                    "radius": radius,
                    "depth": Zc3,
                    "world": world_point,
                    "dist_center": dist_center,
                    "gravity_weight": gravity_weight,
                    "orbit": orbit_descriptor,
                }
            )

        if not projected:
            self._marker_radii = (0.0, 0.0, 0.0)
            return []

        items: List[RenderItem] = []

        for data in projected:
            gravity_weight = float(data.get("gravity_weight", 0.0))

            item = RenderItem(
                sx=float(data["sx"]),
                sy=float(data["sy"]),
                r=float(data["radius"]),
                color=QtGui.QColor("#00C8FF"),
                alpha=1.0,
                depth=float(data["depth"]),
                world=data["world"],
                gravity_weight=gravity_weight,
                role="cloud",
            )
            items.append(item)

            if donut_count > 0 and gravity_weight > 0.0 and data.get("orbit"):
                orbit_info = data["orbit"]
                orbit_item = RenderItem(
                    sx=float(orbit_info["sx"]),
                    sy=float(orbit_info["sy"]),
                    r=float(orbit_info.get("radius", data["radius"])),
                    color=QtGui.QColor("#00C8FF"),
                    alpha=1.0,
                    depth=float(orbit_info.get("depth", data["depth"])),
                    world=data["world"],
                    gravity_weight=float(orbit_info["weight"]),
                    role="orbit",
                )
                items.append(orbit_item)

        self._width = width
        self._height = height

        appearance = self.state.get("appearance", {})
        opacity = float(appearance.get("opacity", 1.0) or 1.0)
        alpha_depth = float(appearance.get("alphaDepth", 0.0) or 0.0)

        # Check for collisions with red circle mask and create imprints
        collision_threshold = radius_red * 0.98  # Slightly inside the red circle
        imprint_radius = float(self.state.get("appearance", {}).get("px", 2.0) or 2.0) * 1.5

        for item in items:
            base_color = self._pick_color(item, now)
            visibility = 1.0
            item.color = base_color
            if alpha_depth > 0:
                t = clamp01(math.atan(max(0.0, item.depth)) / (math.pi / 2))
                depth_alpha = (1 - alpha_depth) + alpha_depth * (1 - t)
            else:
                depth_alpha = 1.0
            item.alpha = clamp01(opacity * depth_alpha * clamp01(visibility))
            
            # Detect when a particle exits the red circle boundary
            if radius_red > 0 and item.role == "cloud":
                dist_from_center = math.hypot(item.sx - cx, item.sy - cy)
                # Identify particle by its seed (index)
                try:
                    particle_idx = int(item.world.seed)
                except Exception:
                    particle_idx = None

                # Check if particle is near or crossing the red circle boundary
                if abs(dist_from_center - collision_threshold) < item.r * 2.0:
                    # Only consider particles leaving the field of view (inside -> outside)
                    prev_pos = self._last_particle_positions.get(particle_idx)
                    if prev_pos is not None:
                        prev_dist = prev_pos[2]
                        # Collision detected: particle crossed the boundary outward
                        if prev_dist < collision_threshold <= dist_from_center:
                            # Create imprint at collision point
                            angle = math.atan2(item.sy - cy, item.sx - cx)
                            collision_x = cx + math.cos(angle) * collision_threshold
                            collision_y = cy + math.sin(angle) * collision_threshold
                            imprint_id = self._imprint_counter
                            self._imprint_counter += 1
                            imprint_color = QtGui.QColor(item.color)
                            self._imprints.append((collision_x, collision_y, imprint_color, imprint_radius, now, imprint_id))
                            # Appliquer limite mémoire douce
                            if len(self._imprints) > self._max_imprints:
                                # Conserver seulement les empreintes les plus récentes
                                self._imprints = self._imprints[-self._max_imprints:]
                            # Créer un orbiteur lié à cette empreinte
                            try:
                                centers, radii, fallback_orbit_radius = self._compute_donut_orbits(width, height)
                                if centers:
                                    bx_idx = 0
                                    best_d2 = float("inf")
                                    for i_btn, (bx_c, by_c) in enumerate(centers):
                                        d2 = (collision_x - bx_c) ** 2 + (collision_y - by_c) ** 2
                                        if d2 < best_d2:
                                            best_d2 = d2
                                            bx_idx = i_btn
                                    bx, by = centers[bx_idx]
                                    base_button_r = 0.0
                                    if bx_idx < len(radii):
                                        base_button_r = float(radii[bx_idx]) or 0.0
                                    orbit_r = max(8.0, (base_button_r or fallback_orbit_radius) + ring_offset)
                                else:
                                    bx, by = cx, cy
                                    orbit_r = max(24.0, min(width, height) * 0.05)
                                ang0 = math.atan2(collision_y - by, collision_x - bx)
                                base_speed = 0.6 + 1.2 * _rand_for_index(idx, 733)
                                angle_speed = max(0.0, base_speed * orbit_speed_multiplier)
                                if snap_mode_cfg != "off" and len(self._orbiters) < self._max_orbiters:
                                    trace_snapshot = list(self._particle_traces.get(particle_idx, []))
                                    if not trace_snapshot or (
                                        abs(trace_snapshot[-1][0] - collision_x) > 0.5
                                        or abs(trace_snapshot[-1][1] - collision_y) > 0.5
                                    ):
                                        trace_snapshot.append((collision_x, collision_y))
                                    if len(trace_snapshot) > self._trail_max_points:
                                        trace_snapshot = trace_snapshot[-self._trail_max_points :]
                                    self._orbiters.append({
                                        "imprint": (collision_x, collision_y),
                                        "imprint_time": float(now),
                                        "color": imprint_color,
                                        "r": max(1.0, item.r * 0.85),
                                        "phase": "out",
                                        "t": 0.0,
                                        "duration_out": float(approach_duration_cfg),
                                        "duration_back": float(return_duration_cfg),
                                        "orbit_center": (bx, by),
                                        "orbit_radius": float(orbit_r),
                                        "angle": float(ang0),
                                        "angle_speed": float(angle_speed),
                                        "base_speed": float(base_speed),
                                        # Exiger au moins un tour complet (2π rad) avant retour
                                        "angle_accum": 0.0,
                                        "required_turns": float(required_turns_cfg),
                                        # Sécurité si angle_speed trop faible
                                        "orbit_elapsed_ms": 0.0,
                                        "max_orbit_ms": float(max_orbit_ms_cfg),
                                        "pos_orbit": (bx + math.cos(ang0) * orbit_r, by + math.sin(ang0) * orbit_r),
                                        "approach_mode": str(approach_traj_cfg),
                                        "return_mode": str(return_traj_cfg),
                                        "trajectory_bend": float(trajectory_bend_cfg),
                                        "arc_direction": str(trajectory_arc_direction_cfg),
                                        "spiral_turns": float(spiral_turns_cfg),
                                        "spiral_tightness": float(spiral_tightness_cfg),
                                        "wave_amplitude": float(wave_amplitude_cfg),
                                        "wave_frequency": float(wave_frequency_cfg),
                                        "trail_blend": float(trail_blend_cfg),
                                        "trail_smoothing": float(trail_smoothing_cfg),
                                        "trail": trace_snapshot,
                                        "imprint_id": imprint_id,
                                        "imprint_cleared": False,
                                        "imprint_radius": float(imprint_radius),
                                    })
                            except Exception:
                                pass
                
                # Update particle position tracking
                self._last_particle_positions[particle_idx] = (item.sx, item.sy, dist_from_center)

        # Mise à jour des orbiters
        orbiters_draw: List[Tuple[float, float, QtGui.QColor, float, float]] = []
        if self._orbiters:
            def _ease_value(mode: str, value: float) -> float:
                value = clamp01(value)
                key = (mode or "default").lower()
                if key in ("none", "linear"):
                    return value
                if key == "ease_in":
                    return pow(value, ease_in_power_cfg)
                if key == "ease_in_out":
                    if value < 0.5:
                        scaled = clamp01(value * 2.0)
                        return 0.5 * pow(scaled, ease_in_power_cfg)
                    scaled = clamp01((1.0 - value) * 2.0)
                    return 1.0 - 0.5 * pow(scaled, ease_out_power_cfg)
                return 1.0 - pow(1.0 - value, ease_out_power_cfg)

            def _trajectory_point(
                mode: str,
                start_x: float,
                start_y: float,
                end_x: float,
                end_y: float,
                t_value: float,
                center: Tuple[float, float] | None,
                orbit_radius: float,
                *,
                bezier_bend: float,
                arc_direction: str,
                spiral_turns: float,
                spiral_tightness: float,
                wave_amplitude: float,
                wave_frequency: float,
                trail: Optional[Sequence[Tuple[float, float]]],
                trail_blend: float,
                trail_smoothing: float,
                phase: str,
            ) -> Tuple[float, float]:
                key = (mode or "line").lower()
                if center is not None:
                    cx, cy = center
                else:
                    cx, cy = 0.0, 0.0
                trail_blend = clamp01(float(trail_blend))
                phase = (phase or "").lower()
                if key == "arc" and center is not None:
                    start_angle = math.atan2(start_y - cy, start_x - cx)
                    end_angle = math.atan2(end_y - cy, end_x - cx)
                    base_delta = (end_angle - start_angle + math.pi) % (2.0 * math.pi) - math.pi
                    direction_key = (arc_direction or "auto").lower()
                    if direction_key in ("cw", "ccw"):
                        diff_full = (end_angle - start_angle) % (2.0 * math.pi)
                        if diff_full <= 0.0:
                            diff_full = 2.0 * math.pi
                        if direction_key == "cw":
                            delta = diff_full - 2.0 * math.pi
                        else:
                            delta = diff_full
                    else:
                        delta = base_delta
                    angle = start_angle + delta * t_value
                    start_radius = math.hypot(start_x - cx, start_y - cy)
                    end_radius = math.hypot(end_x - cx, end_y - cy)
                    radius = start_radius + (end_radius - start_radius) * t_value
                    return cx + math.cos(angle) * radius, cy + math.sin(angle) * radius
                if key == "bezier":
                    mx = (start_x + end_x) / 2.0
                    my = (start_y + end_y) / 2.0
                    dx = end_x - start_x
                    dy = end_y - start_y
                    length = math.hypot(dx, dy)
                    if length <= 1e-6:
                        ctrl_x, ctrl_y = mx, my
                    else:
                        nx = -dy / length
                        ny = dx / length
                        bend = clamp(bezier_bend, -2.0, 2.0)
                        if abs(bend) <= 1e-5:
                            ctrl_x, ctrl_y = mx, my
                        else:
                            scale_factor = 1.0
                            if orbit_radius > 0.0 and length > 0.0:
                                scale_factor = clamp(orbit_radius / max(length, 1.0), 0.3, 2.0)
                            ctrl_x = mx + nx * length * bend * scale_factor
                            ctrl_y = my + ny * length * bend * scale_factor
                    omt = 1.0 - t_value
                    x = omt * omt * start_x + 2.0 * omt * t_value * ctrl_x + t_value * t_value * end_x
                    y = omt * omt * start_y + 2.0 * omt * t_value * ctrl_y + t_value * t_value * end_y
                    return x, y
                if key == "spiral" and center is not None:
                    turns = max(0.01, float(spiral_turns))
                    tight = clamp(float(spiral_tightness), -2.0, 2.0)
                    start_angle = math.atan2(start_y - cy, start_x - cx)
                    end_angle = math.atan2(end_y - cy, end_x - cx)
                    base_radius_start = math.hypot(start_x - cx, start_y - cy)
                    base_radius_end = math.hypot(end_x - cx, end_y - cy)
                    interp_radius = base_radius_start + (base_radius_end - base_radius_start) * t_value
                    angle = start_angle + turns * 2.0 * math.pi * t_value
                    spiral_scale = 1.0 + tight * (t_value - 0.5)
                    radius = max(0.0, interp_radius * spiral_scale)
                    return cx + math.cos(angle) * radius, cy + math.sin(angle) * radius
                if key == "wave":
                    base_x = start_x + (end_x - start_x) * t_value
                    base_y = start_y + (end_y - start_y) * t_value
                    dx = end_x - start_x
                    dy = end_y - start_y
                    length = math.hypot(dx, dy)
                    if length <= 1e-6:
                        return base_x, base_y
                    nx = -dy / length
                    ny = dx / length
                    amp = max(0.0, float(wave_amplitude)) * length * 0.5
                    freq = max(0.0, float(wave_frequency))
                    offset = math.sin(t_value * math.pi * freq) * amp
                    return base_x + nx * offset, base_y + ny * offset
                if key == "initial_path":
                    path_points: List[Tuple[float, float]] = []
                    if trail:
                        if phase == "out":
                            core_path = list(reversed(trail))
                        else:
                            core_path = list(trail)
                        # Filtrer les doublons consécutifs
                        filtered: List[Tuple[float, float]] = []
                        for px, py in core_path:
                            if not filtered or (abs(filtered[-1][0] - px) > 0.01 or abs(filtered[-1][1] - py) > 0.01):
                                filtered.append((px, py))
                        path_points.extend(filtered)
                    if not path_points or (abs(path_points[-1][0] - end_x) > 0.01 or abs(path_points[-1][1] - end_y) > 0.01):
                        path_points.append((end_x, end_y))
                    path_points.insert(0, (start_x, start_y))
                    if trail_smoothing > 0.0 and len(path_points) > 3:
                        radius = max(1, int(round(1 + trail_smoothing * 4)))
                        smoothed: List[Tuple[float, float]] = []
                        for idx in range(len(path_points)):
                            start_idx = max(0, idx - radius)
                            end_idx = min(len(path_points), idx + radius + 1)
                            window = path_points[start_idx:end_idx]
                            if not window:
                                continue
                            sx = sum(p[0] for p in window) / len(window)
                            sy = sum(p[1] for p in window) / len(window)
                            smoothed.append((sx, sy))
                        if smoothed:
                            path_points = smoothed
                    distances = [0.0]
                    total = 0.0
                    for idx in range(len(path_points) - 1):
                        seg = math.hypot(
                            path_points[idx + 1][0] - path_points[idx][0],
                            path_points[idx + 1][1] - path_points[idx][1],
                        )
                        total += seg
                        distances.append(total)
                    if total <= 1e-6:
                        path_x, path_y = path_points[-1]
                    else:
                        target = clamp(t_value * total, 0.0, total)
                        path_x, path_y = path_points[-1]
                        for idx in range(len(path_points) - 1):
                            seg_start = distances[idx]
                            seg_end = distances[idx + 1]
                            if seg_end >= target:
                                seg_len = max(1e-6, seg_end - seg_start)
                                local = (target - seg_start) / seg_len
                                sx = path_points[idx][0] + (path_points[idx + 1][0] - path_points[idx][0]) * local
                                sy = path_points[idx][1] + (path_points[idx + 1][1] - path_points[idx][1]) * local
                                path_x, path_y = sx, sy
                                break
                    lin_x = start_x + (end_x - start_x) * t_value
                    lin_y = start_y + (end_y - start_y) * t_value
                    blend = trail_blend
                    return lin_x * (1.0 - blend) + path_x * blend, lin_y * (1.0 - blend) + path_y * blend
                return start_x + (end_x - start_x) * t_value, start_y + (end_y - start_y) * t_value

            survivors: List[Dict[str, object]] = []
            snap_mode_lower = snap_mode_cfg.lower()
            detach_mode_lower = detach_mode_cfg.lower()
            for ob in self._orbiters:
                try:
                    phase = str(ob.get("phase", "out"))
                    t_phase = float(ob.get("t", 0.0))
                    ix, iy = ob.get("imprint", (cx, cy))  # type: ignore[assignment]
                    bx, by = ob.get("orbit_center", (cx, cy))  # type: ignore[assignment]
                    orbit_r = float(ob.get("orbit_radius", 32.0))
                    angle = float(ob.get("angle", 0.0))
                    base_speed = float(ob.get("base_speed", ob.get("angle_speed", 1.0)))
                    if not math.isfinite(base_speed):
                        base_speed = 0.0
                    angle_speed = max(0.0, base_speed * orbit_speed_multiplier)
                    ob["base_speed"] = base_speed
                    ob["angle_speed"] = angle_speed
                    pos_orbit = ob.get("pos_orbit")  # type: ignore[assignment]
                    if not isinstance(pos_orbit, tuple) or len(pos_orbit) != 2:
                        pos_orbit = (bx + math.cos(angle) * orbit_r, by + math.sin(angle) * orbit_r)
                    px, py = float(pos_orbit[0]), float(pos_orbit[1])
                    r_draw = float(ob.get("r", 2.0))
                    qcolor = ob.get("color", QtGui.QColor("#FFFFFF"))  # type: ignore[assignment]
                    if not isinstance(qcolor, QtGui.QColor):
                        qcolor = QtGui.QColor(str(qcolor))

                    spiral_turns = float(ob.get("spiral_turns", spiral_turns_cfg))
                    spiral_tightness = float(ob.get("spiral_tightness", spiral_tightness_cfg))
                    wave_amplitude = float(ob.get("wave_amplitude", wave_amplitude_cfg))
                    wave_frequency = float(ob.get("wave_frequency", wave_frequency_cfg))
                    trail_blend = float(ob.get("trail_blend", trail_blend_cfg))
                    trail_smoothing = float(ob.get("trail_smoothing", trail_smoothing_cfg))
                    trail_data = ob.get("trail")
                    imprint_id = ob.get("imprint_id")
                    imprint_cleared = bool(ob.get("imprint_cleared", False))
                    ob["spiral_turns"] = spiral_turns
                    ob["spiral_tightness"] = spiral_tightness
                    ob["wave_amplitude"] = wave_amplitude
                    ob["wave_frequency"] = wave_frequency
                    ob["trail_blend"] = trail_blend
                    ob["trail_smoothing"] = trail_smoothing

                    ob["duration_out"] = float(approach_duration_cfg)
                    ob["duration_back"] = float(return_duration_cfg)
                    ob["required_turns"] = float(required_turns_cfg)
                    ob["max_orbit_ms"] = float(max_orbit_ms_cfg)
                    ob["approach_mode"] = str(approach_traj_cfg)
                    ob["return_mode"] = str(return_traj_cfg)
                    ob["trajectory_bend"] = float(trajectory_bend_cfg)
                    ob["arc_direction"] = str(trajectory_arc_direction_cfg)

                    imprint_radius = float(ob.get("imprint_radius", r_draw * 1.5))

                    if phase == "out":
                        if snap_mode_lower == "off":
                            phase = "orbit"
                            t_phase = 0.0
                            sx, sy = px, py
                        else:
                            dur = max(1.0, float(ob.get("duration_out", approach_duration_cfg)))
                            t_phase = min(1.0, t_phase + dt * 1000.0 / dur)
                            t_eased = _ease_value(snap_mode_lower, t_phase)
                            traj_mode = str(ob.get("approach_mode", approach_traj_cfg))
                            sx, sy = _trajectory_point(
                                traj_mode,
                                ix,
                                iy,
                                px,
                                py,
                                t_eased,
                                (bx, by),
                                orbit_r,
                                bezier_bend=float(ob.get("trajectory_bend", trajectory_bend_cfg)),
                                arc_direction=str(ob.get("arc_direction", trajectory_arc_direction_cfg)),
                                spiral_turns=spiral_turns,
                                spiral_tightness=spiral_tightness,
                                wave_amplitude=wave_amplitude,
                                wave_frequency=wave_frequency,
                                trail=trail_data if isinstance(trail_data, Sequence) else None,
                                trail_blend=trail_blend,
                                trail_smoothing=trail_smoothing,
                                phase="out",
                            )
                            if t_phase >= 1.0:
                                phase = "orbit"
                                t_phase = 0.0
                    elif phase == "orbit":
                        dtheta = angle_speed * dt
                        angle += dtheta
                        px = bx + math.cos(angle) * orbit_r
                        py = by + math.sin(angle) * orbit_r
                        sx, sy = px, py
                        ob["angle"] = angle
                        ob["pos_orbit"] = (px, py)
                        accum = float(ob.get("angle_accum", 0.0)) + abs(dtheta)
                        ob["angle_accum"] = accum
                        elapsed = float(ob.get("orbit_elapsed_ms", 0.0)) + dt * 1000.0
                        ob["orbit_elapsed_ms"] = elapsed
                        required_turns = max(0.0, float(ob.get("required_turns", required_turns_cfg)))
                        target = required_turns * (2.0 * math.pi)
                        max_ms = float(ob.get("max_orbit_ms", max_orbit_ms_cfg))
                        if target <= 0.0 or accum >= target or elapsed >= max_ms:
                            phase = "back"
                            t_phase = 0.0
                    else:
                        if detach_mode_lower == "off":
                            if not imprint_cleared:
                                self._remove_imprint_by_id(imprint_id if isinstance(imprint_id, int) else None)
                                imprint_cleared = True
                            phase = "done"
                            sx, sy = ix, iy
                        else:
                            dur = max(1.0, float(ob.get("duration_back", return_duration_cfg)))
                            t_phase = min(1.0, t_phase + dt * 1000.0 / dur)
                            t_eased = _ease_value(detach_mode_lower, t_phase)
                            traj_mode = str(ob.get("return_mode", return_traj_cfg))
                            sx, sy = _trajectory_point(
                                traj_mode,
                                px,
                                py,
                                ix,
                                iy,
                                t_eased,
                                (bx, by),
                                orbit_r,
                                bezier_bend=float(ob.get("trajectory_bend", trajectory_bend_cfg)),
                                arc_direction=str(ob.get("arc_direction", trajectory_arc_direction_cfg)),
                                spiral_turns=spiral_turns,
                                spiral_tightness=spiral_tightness,
                                wave_amplitude=wave_amplitude,
                                wave_frequency=wave_frequency,
                                trail=trail_data if isinstance(trail_data, Sequence) else None,
                                trail_blend=trail_blend,
                                trail_smoothing=trail_smoothing,
                                phase="back",
                            )
                            if not imprint_cleared:
                                if math.hypot(sx - ix, sy - iy) <= max(2.0, imprint_radius * 1.1):
                                    self._remove_imprint_by_id(
                                        imprint_id if isinstance(imprint_id, int) else None
                                    )
                                    imprint_cleared = True
                            if t_phase >= 1.0:
                                if not imprint_cleared:
                                    self._remove_imprint_by_id(imprint_id if isinstance(imprint_id, int) else None)
                                    imprint_cleared = True
                                phase = "done"

                    if phase == "done" and not imprint_cleared:
                        self._remove_imprint_by_id(imprint_id if isinstance(imprint_id, int) else None)
                        imprint_cleared = True

                    if phase != "done":
                        ob["phase"] = phase
                        ob["t"] = t_phase
                        ob["imprint_cleared"] = imprint_cleared
                        if phase == "orbit":
                            alpha_o = 0.95
                        elif phase == "out":
                            alpha_o = 0.5 + 0.45 * t_phase
                        else:
                            alpha_o = 0.95 - 0.10 * t_phase
                        orbiters_draw.append((sx, sy, qcolor, r_draw, alpha_o))
                        survivors.append(ob)
                except Exception:
                    continue
            self._orbiters = survivors
            self._orbiters_draw = orbiters_draw
        else:
            self._orbiters_draw = []

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
        self._gl: Optional[object] = None
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

    def _compute_marker_radii(self, width: float, height: float) -> Tuple[float, float, float]:
        """Return the radii of the red, yellow and blue marker circles."""

        if width <= 0.0 or height <= 0.0:
            return 0.0, 0.0, 0.0
        min_dim = max(1.0, min(width, height))
        base_area = (width * height) / 3.0
        base_radius = math.sqrt(max(base_area, 0.0) / math.pi)
        radius_red = base_radius * 0.5
        radius_yellow = radius_red * 1.15
        radius_blue = radius_yellow * 1.10
        max_radius = min_dim / 2.0
        radius_red = min(radius_red, max_radius)
        radius_yellow = min(radius_yellow, max_radius)
        radius_blue = min(radius_blue, max_radius)

        system = self.engine.state.get("system", {})
        # The widget stores the live state on the engine instance. Use
        # engine.state here instead of self.state (which only exists on the
        # engine) to avoid AttributeError on the widget instances.
        indicator_cfg = self.engine.state.get("indicator")
        yellow_override_ratio: Optional[float] = None
        if isinstance(indicator_cfg, Mapping):
            raw_yellow = indicator_cfg.get("yellowCircleRatio")
            try:
                yellow_override_ratio = float(raw_yellow)
            except (TypeError, ValueError):
                yellow_override_ratio = None
            if yellow_override_ratio is not None:
                yellow_override_ratio = clamp(yellow_override_ratio, 0.0, 0.5)

        marker_cfg = system.get("markerCircles")
        if isinstance(marker_cfg, Mapping):
            def _resolve(key: str, fallback: float) -> float:
                raw = marker_cfg.get(key, fallback / min_dim)
                try:
                    ratio = float(raw)
                except (TypeError, ValueError):
                    ratio = fallback / min_dim
                ratio = clamp(ratio, 0.0, 0.5)
                return ratio * min_dim

            radius_red = _resolve("red", radius_red)
            radius_yellow = _resolve("yellow", radius_yellow)
            # Blue circle now uses donutRadiusRatio directly
            donut_radius_ratio = system.get("donutRadiusRatio", 0.35)
            try:
                donut_radius_ratio = float(donut_radius_ratio)
            except (TypeError, ValueError):
                donut_radius_ratio = 0.35
            donut_radius_ratio = clamp(donut_radius_ratio, 0.05, 0.90)
            radius_blue = min_dim * donut_radius_ratio

        if yellow_override_ratio is not None:
            radius_yellow = yellow_override_ratio * min_dim

        return radius_red, radius_yellow, radius_blue

    def update_donut_layout(
        self,
        centers: Sequence[Tuple[float, float]],
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        radii: Optional[Sequence[float]] = None,
    ) -> None:
        """Forward the donut button layout from the host window to the engine."""

        if width is None:
            width = int(self.width())
        if height is None:
            height = int(self.height())
        try:
            self.engine.update_donut_layout(int(width), int(height), centers, radii=radii)
        except Exception:
            pass

    # ------------------------------------------------------------------ OpenGL hooks
    def initializeGL(self) -> None:  # pragma: no cover - requires GUI context
        self._gl, _ = _create_opengl_functions()
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

    def reset_visual_state(self) -> None:
        """Expose a hook for the controller to reset transient rendering state."""

        self.engine.reset_visual_state()
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
        radius_red, radius_yellow, radius_blue = self._compute_marker_radii(width, height)
        
        # Apply circular mask based on red circle
        center_x = width / 2.0
        center_y = height / 2.0
        
        # Draw imprints first (under everything)
        if self.engine._imprints:
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            painter.setPen(QtCore.Qt.NoPen)
            current_time = self.engine.now_ms
            imprints_to_keep = []
            for imp_x, imp_y, imp_color, imp_radius, imp_time, imp_id in self.engine._imprints:
                # Fade out old imprints over time (optional, or keep them permanent)
                age_sec = (current_time - imp_time) / 1000.0
                # Make imprints permanent by not fading them
                alpha = 0.6  # Permanent opacity
                if alpha > 0.01:
                    color = QtGui.QColor(imp_color)
                    color.setAlphaF(alpha)
                    painter.setBrush(color)
                    painter.drawEllipse(QtCore.QRectF(imp_x - imp_radius, imp_y - imp_radius, imp_radius * 2, imp_radius * 2))
                    imprints_to_keep.append((imp_x, imp_y, imp_color, imp_radius, imp_time, imp_id))
            self.engine._imprints = imprints_to_keep

        # Dessiner les orbiters avant le clipping (ils peuvent dépasser le cercle)
        if self.engine._orbiters_draw:
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            painter.setPen(QtCore.Qt.NoPen)
            for sx, sy, color, r_draw, alpha in self.engine._orbiters_draw:
                col = QtGui.QColor(color)
                col.setAlphaF(clamp01(alpha))
                painter.setBrush(col)
                painter.drawEllipse(QtCore.QRectF(sx - r_draw, sy - r_draw, r_draw * 2, r_draw * 2))
        
        # Apply circular mask based on red circle
        if radius_red > 0:
            # Create circular clipping path
            clip_path = QtGui.QPainterPath()
            clip_path.addEllipse(
                QtCore.QRectF(
                    center_x - radius_red,
                    center_y - radius_red,
                    radius_red * 2.0,
                    radius_red * 2.0
                )
            )
            painter.setClipPath(clip_path)
        
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

        # Remove clipping for marker circles
        painter.setClipping(False)

        indicator_cfg = self.engine.state.get("indicator", {})
        donut_centers, _donut_radii, fallback_orbit_radius = self.engine._compute_donut_orbits(width, height)
        donut_count = len(donut_centers)

        if donut_count > 0 and isinstance(indicator_cfg, Mapping):
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            center_cfg = indicator_cfg.get("centerLines", {})
            selected_indices: List[int] = []
            if isinstance(center_cfg, Mapping):
                all_flag = bool(center_cfg.get("all", False))
                if all_flag:
                    selected_indices = list(range(donut_count))
                else:
                    buttons_cfg = center_cfg.get("buttons", {})
                    if isinstance(buttons_cfg, Mapping):
                        for key, value in buttons_cfg.items():
                            if not value:
                                continue
                            try:
                                idx = int(key) - 1
                            except Exception:
                                continue
                            if 0 <= idx < donut_count:
                                selected_indices.append(idx)
            if selected_indices:
                line_color = QtGui.QColor(255, 255, 0, 180)
                pen = QtGui.QPen(line_color, 1.5)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(QtCore.Qt.NoBrush)
                for idx in selected_indices:
                    bx, by = donut_centers[idx]
                    painter.drawLine(QtCore.QLineF(center_x, center_y, bx, by))

            orbital_cfg = indicator_cfg.get("orbitalZones", {})
            if isinstance(orbital_cfg, Mapping) and orbital_cfg.get("enabled", True):
                raw_diameters = orbital_cfg.get("diameters", [])
                radii: List[float] = []
                if not isinstance(raw_diameters, Sequence):
                    raw_diameters = []
                for idx in range(donut_count):
                    if idx < len(raw_diameters):
                        try:
                            diameter = float(raw_diameters[idx])
                        except (TypeError, ValueError):
                            diameter = fallback_orbit_radius * 2.0
                    else:
                        diameter = fallback_orbit_radius * 2.0
                    radius = max(0.0, float(diameter) * 0.5)
                    radii.append(radius)
                pen = QtGui.QPen(QtGui.QColor(0, 255, 0, 170), 1.5)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(QtCore.Qt.NoBrush)
                for idx, radius in enumerate(radii):
                    if radius <= 0.5:
                        continue
                    bx, by = donut_centers[idx]
                    painter.drawEllipse(QtCore.QRectF(bx - radius, by - radius, radius * 2.0, radius * 2.0))

        # Draw permanent concentric marker circles centred on the viewport
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        painter.setBrush(QtCore.Qt.NoBrush)

        if width > 0 and height > 0:
            def _draw_marker_circle(color: QtGui.QColor, radius: float) -> None:
                if radius <= 0.0:
                    return
                diameter = radius * 2.0
                painter.setPen(QtGui.QPen(color, 2.0))
                painter.drawEllipse(QtCore.QRectF(center_x - radius, center_y - radius, diameter, diameter))

            radius_red, radius_yellow, radius_blue = self.engine.marker_radii(width, height)
            if radius_red > 0:
                _draw_marker_circle(QtGui.QColor("red"), radius_red)
            if radius_yellow > 0:
                _draw_marker_circle(QtGui.QColor("yellow"), radius_yellow)
            if radius_blue > 0:
                _draw_marker_circle(QtGui.QColor("blue"), radius_blue)


class _OpenGLViewWidget(QtWidgets.QOpenGLWidget, _ViewWidgetBase):
    """OpenGL-backed renderer when the system can create a GL context."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        QtWidgets.QOpenGLWidget.__init__(self, parent)
        self._gl: Optional[object] = None
        self._init_view_widget()

    def initializeGL(self) -> None:  # pragma: no cover - requires GUI context
        self._gl, error = _create_opengl_functions()
        if error is not None:  # pragma: no cover - depends on bindings/runtime
            print(
                f"[Dyxten][WARN] OpenGL initialisation failed: {error}. Falling back to raster clear handling.",
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

    env_backend = os.environ.get("DYXTEN_FORCE_BACKEND", "").strip().lower()
    if env_backend == "raster":
        return False
    if env_backend == "opengl":
        return True

    if os.environ.get("DYXTEN_FORCE_RASTER", "").strip().lower() in {"1", "true", "yes"}:
        return False
    if os.environ.get("DYXTEN_FORCE_OPENGL", "").strip().lower() in {"1", "true", "yes"}:
        return True
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

for name, generator in _DEFAULT_GENERATORS.items():
    if name not in DyxtenEngine._GEOMETRY_GENERATORS:
        DyxtenEngine._GEOMETRY_GENERATORS[name] = _wrap_builtin_generator(generator)


