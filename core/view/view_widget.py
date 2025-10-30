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

This file provides :class:`DyxtenViewWidget`, a ``QWidget`` subclass that
exposes the ``set_params`` method mirroring the JavaScript API.  It keeps the
same data-model as the web version which greatly simplifies interoperability
with the existing controller code.

The implementation favours a direct translation of the JavaScript logic to keep
behaviour parity.  The goal is not to micro-optimise the renderer but to offer
feature completeness and ease of maintenance.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

from ..donut import DEFAULT_DONUT_BUTTON_COUNT, default_donut_config, sanitize_donut_state


GeometryGenerator = Callable[[Mapping[str, float], int], List["Point3D"]]

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


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def to_rad(deg: float) -> float:
    return deg * math.pi / 180.0


# ---------------------------------------------------------------------------
# Utility helpers translated from the JavaScript implementation


def _sgnpow(u: float, p: float) -> float:
    a = abs(u)
    expo = 2.0 / max(1e-6, p)
    return math.copysign(a ** expo, u)


def _parse_number_list(text: str | None) -> List[float]:
    if not text:
        return []
    numbers: List[float] = []
    for token in text.replace("\n", " ").replace(";", " ").split():
        try:
            value = float(token)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            numbers.append(value)
    return numbers


def _parse_vector_list(text: str | None) -> List[Tuple[float, float, float]]:
    if not text:
        return []
    tokens = [token.strip() for token in text.replace("\r", "").split(";")]
    if not [token for token in tokens if token]:
        flat = _parse_number_list(text)
        if len(flat) >= 3:
            return [(flat[0], flat[1], flat[2])]
        return []
    vectors: List[Tuple[float, float, float]] = []
    for token in tokens:
        if not token:
            continue
        parts = [p for p in token.replace(",", " ").split() if p]
        values: List[float] = []
        for part in parts:
            try:
                values.append(float(part))
            except (TypeError, ValueError):
                continue
        while len(values) < 3:
            values.append(0.0)
        if values:
            vectors.append((values[0], values[1], values[2]))
    return vectors


def _eval_expression(expr: str | None, variables: Mapping[str, float]) -> float:
    if not expr or not expr.strip():
        return 1.0
    try:
        code = compile(expr, "<dyxten-expr>", "eval")
        return float(eval(code, {"__builtins__": {}}, {**math.__dict__, **variables}))
    except Exception:
        return 0.0


def _norm_scale(vector: Tuple[float, float, float], radius: float) -> Tuple[float, float, float]:
    length = math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2) or 1.0
    return (
        radius * vector[0] / length,
        radius * vector[1] / length,
        radius * vector[2] / length,
    )


def _clamp_count(value: int, cap: int) -> int:
    if cap and cap > 0:
        return min(value, cap)
    return value


def _rand_for_index(index: int, salt: int = 0) -> float:
    s = index * 12.9898 + salt * 78.233
    x = math.sin(s) * 43758.5453
    return x - math.floor(x)


def _default_state() -> Dict[str, dict]:
    return {
        "camera": {
            "camRadius": 3.2,
            "camHeightDeg": 15,
            "camTiltDeg": 0,
            "omegaDegPerSec": 20,
            "fov": 600,
        },
        "geometry": {
            "topology": "torus",
            "R": 1.0,
            "lat": 64,
            "lon": 64,
            "N": 4096,
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
        self._transparent = True
        self._width = 1
        self._height = 1
        self.rebuild_geometry()

    # ------------------------------------------------------------------ helpers
    @property
    def now_ms(self) -> float:
        return (time.perf_counter() - self._start_time) * 1000.0

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

        cos_theta = math.cos(cam_theta)
        sin_theta = math.sin(cam_theta)
        cos_height = math.cos(cam_height)
        sin_height = math.sin(cam_height)
        cos_tilt = math.cos(cam_tilt)
        sin_tilt = math.sin(cam_tilt)

        scale = 0.45 * min(width, height)
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

            Zc3 += cam_radius
            if Zc3 <= 0.01:
                continue
            inv = fov / Zc3
            sx = cx + Xc3 * inv * scale
            sy = cy + Yc3 * inv * scale
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
        return items


class DyxtenViewWidget(QtWidgets.QWidget):
    """Widget displaying the animated donut particle system."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, False)
        self.engine = DyxtenEngine()
        self._items: List[RenderItem] = []
        self._shape = "circle"
        self._transparent = True
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)

    # ------------------------------------------------------------------ API
    def set_params(self, payload: Mapping[str, object]) -> None:
        previous_shape = self._shape
        self.engine.set_params(payload)
        appearance = self.engine.state.get("appearance", {})
        self._shape = appearance.get("shape", "circle")
        if previous_shape != self._shape:
            self.update()

    def current_donut(self) -> dict:
        return self.engine.state.get("donut", default_donut_config())

    def set_transparent(self, enabled: bool) -> None:
        self._transparent = bool(enabled)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, enabled)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, enabled)
        self.update()

    # ------------------------------------------------------------------ Qt events
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        if not self._transparent:
            painter.fillRect(self.rect(), QtGui.QColor("black"))
        width = max(1, self.width())
        height = max(1, self.height())
        items = self.engine.step(width, height)
        for item in items:
            color = QtGui.QColor(item.color)
            color.setAlphaF(clamp01(item.alpha))
            painter.setBrush(color)
            painter.setPen(QtCore.Qt.NoPen)
            if self._shape == "square":
                painter.drawRect(QtCore.QRectF(item.sx - item.r, item.sy - item.r, item.r * 2, item.r * 2))
            else:
                painter.drawEllipse(QtCore.QRectF(item.sx - item.r, item.sy - item.r, item.r * 2, item.r * 2))
        painter.end()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.update()


def _gen_uv_sphere(geo: Mapping[str, float], cap: int) -> List[Point3D]:
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
    return points[:_clamp_count(len(points), cap)]


def _gen_fibo_sphere(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    phi_g = float(geo.get("phi_g", 0.0) or 0.0)
    denom = max(1, count - 1)
    out: List[Point3D] = []
    for i in range(count):
        z = 1 - (2 * i) / denom
        r = math.sqrt(max(0.0, 1 - z * z))
        phi = i * phi_g
        out.append(
            Point3D(
                radius * r * math.cos(phi),
                radius * z,
                radius * r * math.sin(phi),
            )
        )
    return out


def _gen_disk_phyllo(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    phi_g = float(geo.get("phi_g", 0.0) or 0.0)
    out: List[Point3D] = []
    denom = max(1, count - 1)
    for k in range(count):
        theta = k * phi_g
        r = radius * math.sqrt(k / denom)
        out.append(Point3D(r * math.cos(theta), 0.0, r * math.sin(theta)))
    return out


def _gen_archimede_spiral(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(2, int(geo.get("N", 0) or 0)), cap)
    theta_max = max(0.1, float(geo.get("theta_max", 0.0) or (math.pi * 6)))
    arch_a = float(geo.get("arch_a", 0.0) or 0.0)
    arch_b = float(geo.get("arch_b", 0.0) or 0.0)
    radius = float(geo.get("R", 1.0))
    denom = arch_a + arch_b * theta_max
    scale = radius / abs(denom) if denom != 0 else radius
    out: List[Point3D] = []
    for i in range(count):
        t = 0.0 if count == 1 else theta_max * i / (count - 1)
        r = abs(arch_a + arch_b * t) * scale
        out.append(Point3D(r * math.cos(t), 0.0, r * math.sin(t)))
    return out


def _gen_log_spiral(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(2, int(geo.get("N", 0) or 0)), cap)
    theta_max = max(0.1, float(geo.get("theta_max", 0.0) or (math.pi * 6)))
    log_a = float(geo.get("log_a", 0.0) or 0.0)
    log_b = float(geo.get("log_b", 0.0) or 0.0)
    radius = float(geo.get("R", 1.0))
    base = math.exp(log_b * theta_max)
    scale = radius / (log_a * base) if log_a * base != 0 else radius
    out: List[Point3D] = []
    for i in range(count):
        t = 0.0 if count == 1 else theta_max * i / (count - 1)
        r = abs(log_a * math.exp(log_b * t)) * scale
        out.append(Point3D(r * math.cos(t), 0.0, r * math.sin(t)))
    return out


def _gen_rose_curve(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(2, int(geo.get("N", 0) or 0)), cap)
    theta_max = max(0.1, float(geo.get("theta_max", 0.0) or (2 * math.pi)))
    rose_k = float(geo.get("rose_k", 0.0) or 0.0)
    radius = float(geo.get("R", 1.0))
    out: List[Point3D] = []
    for i in range(count):
        t = 0.0 if count == 1 else theta_max * i / (count - 1)
        r = abs(math.cos(rose_k * t)) * radius
        out.append(Point3D(r * math.cos(t), 0.0, r * math.sin(t)))
    return out


def _superformula2d(theta: float, m: float, a: float, b: float, n1: float, n2: float, n3: float) -> float:
    part1 = abs(math.cos((m * theta) / 4.0) / (a or 1.0)) ** n2
    part2 = abs(math.sin((m * theta) / 4.0) / (b or 1.0)) ** n3
    return (part1 + part2) ** (-1.0 / max(1e-6, n1))


def _gen_superformula_2d(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(2, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    m = float(geo.get("sf2_m", 0.0) or 0.0)
    a = float(geo.get("sf2_a", 0.0) or 1.0)
    b = float(geo.get("sf2_b", 0.0) or 1.0)
    n1 = float(geo.get("sf2_n1", 0.0) or 0.5)
    n2 = float(geo.get("sf2_n2", 0.0) or 0.5)
    n3 = float(geo.get("sf2_n3", 0.0) or 0.5)
    out: List[Point3D] = []
    for i in range(count):
        theta = (i / count) * 2.0 * math.pi
        r = radius * _superformula2d(theta, m, a, b, n1, n2, n3)
        out.append(Point3D(r * math.cos(theta), 0.0, r * math.sin(theta)))
    return out


def _gen_density_warp(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    density_expr = geo.get("density_pdf")
    out: List[Point3D] = []
    attempts = 0
    max_attempts = count * 20
    while len(out) < count and attempts < max_attempts:
        attempts += 1
        u = random.random()
        r = math.sqrt(u)
        pdf = max(0.0, _eval_expression(density_expr, {"r": r, "u": u}))
        if pdf <= 0:
            continue
        if random.random() > clamp01(pdf):
            continue
        theta = random.random() * 2.0 * math.pi
        radius_abs = radius * r
        out.append(Point3D(radius_abs * math.cos(theta), 0.0, radius_abs * math.sin(theta)))
    return out


def _gen_poisson_disk(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    min_dist = max(0.0, float(geo.get("poisson_dmin", 0.0) or 0.0)) * radius
    out: List[Point3D] = []
    tries = 0
    max_tries = count * 50
    while len(out) < count and tries < max_tries:
        tries += 1
        r = radius * math.sqrt(random.random())
        theta = random.random() * 2.0 * math.pi
        point = Point3D(r * math.cos(theta), 0.0, r * math.sin(theta))
        ok = True
        for existing in out:
            dx = point.x - existing.x
            dz = point.z - existing.z
            if dx * dx + dz * dz < min_dist * min_dist:
                ok = False
                break
        if ok:
            out.append(point)
    return out


def _gen_lissajous_disk(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(2, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    a = max(1, int(geo.get("lissajous_a", 0) or 0))
    b = max(1, int(geo.get("lissajous_b", 0) or 0))
    phase = float(geo.get("lissajous_phase", 0.0) or 0.0)
    out: List[Point3D] = []
    for i in range(count):
        t = (i / count) * 2.0 * math.pi
        x = math.cos(a * t + phase)
        z = math.sin(b * t)
        out.append(Point3D(radius * x, 0.0, radius * z))
    return out


def _gen_torus(geo: Mapping[str, float], cap: int, scale_radius: float = 1.0) -> List[Point3D]:
    Rmaj = float(geo.get("R_major", 0.0) or 1.2)
    rmin = float(geo.get("r_minor", 0.0) or 0.45)
    lat_steps = max(3, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    radius = float(geo.get("R", 1.0)) * scale_radius
    out: List[Point3D] = []
    for i in range(lat_steps):
        v = i / lat_steps
        theta = v * 2.0 * math.pi
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        ring = Rmaj + rmin * cos_theta
        for j in range(lon_steps):
            u = j / lon_steps
            phi = u * 2.0 * math.pi
            cos_phi = math.cos(phi)
            sin_phi = math.sin(phi)
            out.append(
                Point3D(
                    radius * ring * cos_phi,
                    radius * (rmin * sin_theta),
                    radius * ring * sin_phi,
                )
            )
    return out[:_clamp_count(len(out), cap)]


def _gen_double_torus(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    primary = _gen_torus(geo, cap)
    secondary_geo = dict(geo)
    secondary_geo["R_major"] = float(geo.get("R_major2", geo.get("R_major", 1.2)))
    secondary = _gen_torus(secondary_geo, cap)
    combined = primary + secondary
    return combined[:_clamp_count(len(combined), cap)]


def _gen_torus_knot(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(50, int(geo.get("N", 0) or 0)), cap)
    p = max(1, int(geo.get("torus_knot_p", 0) or 0))
    q = max(1, int(geo.get("torus_knot_q", 0) or 0))
    R_major = float(geo.get("R_major", 1.0) or 1.0)
    r_minor = float(geo.get("r_minor", 0.2) or 0.2)
    radius = float(geo.get("R", 1.0))
    total = 2.0 * math.pi * p
    out: List[Point3D] = []
    for i in range(count):
        t = total * i / count
        cos_q = math.cos(q * t / p)
        sin_q = math.sin(q * t / p)
        x = (R_major + r_minor * cos_q) * math.cos(t)
        y = (R_major + r_minor * cos_q) * math.sin(t)
        z = r_minor * sin_q
        out.append(Point3D(x * radius, y * radius, z * radius))
    return out


def _gen_strip_twist(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    lat_steps = max(3, int(geo.get("lat", 0) or 0))
    lon_steps = max(20, int(geo.get("lon", 0) or 0))
    half_w = float(geo.get("strip_w", 0.0) or 0.0) / 2.0
    twist_n = float(geo.get("strip_n", 0.0) or 0.0)
    radius = float(geo.get("R", 1.0))
    out: List[Point3D] = []
    for i in range(lon_steps):
        u = i / lon_steps * 2.0 * math.pi
        for j in range(lat_steps):
            v = -half_w + (j / (lat_steps - 1 if lat_steps > 1 else 1)) * (2 * half_w)
            angle = twist_n * u / 2.0
            x = (radius + v * math.cos(angle)) * math.cos(u)
            y = v * math.sin(angle)
            z = (radius + v * math.cos(angle)) * math.sin(u)
            out.append(Point3D(x, y, z))
    return out[:_clamp_count(len(out), cap)]


def _gen_klein_bottle(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    lat_steps = max(3, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    R_major = float(geo.get("R_major", 0.0) or 0.0)
    r_minor = float(geo.get("r_minor", 0.0) or 0.0)
    out: List[Point3D] = []
    for i in range(lon_steps):
        v = i / lon_steps * 2.0 * math.pi
        sin_v = math.sin(v)
        sin_2v = math.sin(2 * v)
        for j in range(lat_steps):
            u = j / lat_steps * 2.0 * math.pi
            cos_u = math.cos(u)
            sin_u = math.sin(u)
            cos_u_half = math.cos(u / 2.0)
            sin_u_half = math.sin(u / 2.0)
            x = (R_major + r_minor * cos_u_half * sin_v - r_minor * sin_u_half * sin_2v) * cos_u
            y = (R_major + r_minor * cos_u_half * sin_v - r_minor * sin_u_half * sin_2v) * sin_u
            z = r_minor * sin_u_half * sin_v + r_minor * cos_u_half * sin_2v
            out.append(Point3D(x, y, z))
    return out[:_clamp_count(len(out), cap)]


DyxtenEngine._GEOMETRY_GENERATORS = {
    "uv_sphere": _gen_uv_sphere,
    "fibo_sphere": _gen_fibo_sphere,
    "disk_phyllotaxis": _gen_disk_phyllo,
    "archimede_spiral": _gen_archimede_spiral,
    "log_spiral": _gen_log_spiral,
    "rose_curve": _gen_rose_curve,
    "superformula_2D": _gen_superformula_2d,
    "density_warp_disk": _gen_density_warp,
    "poisson_disk": _gen_poisson_disk,
    "lissajous_disk": _gen_lissajous_disk,
    "torus": _gen_torus,
    "double_torus": _gen_double_torus,
    "torus_knot": _gen_torus_knot,
    "strip_twist": _gen_strip_twist,
    "klein_bottle": _gen_klein_bottle,
}
