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

import json
import math
import os
import random
import sys
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


def _parse_bbox(text: str | None) -> Tuple[float, float, float, float]:
    values = _parse_number_list(text)
    if len(values) >= 4:
        return (values[0], values[1], values[2], values[3])
    return (-1.0, 1.0, -1.0, 1.0)


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


def _normalize(vec: Tuple[float, float, float]) -> Tuple[float, float, float]:
    length = math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2) or 1.0
    return (vec[0] / length, vec[1] / length, vec[2] / length)


def _scale(vec: Tuple[float, float, float], scale: float) -> Tuple[float, float, float]:
    return (vec[0] * scale, vec[1] * scale, vec[2] * scale)


def _mix(a: Tuple[float, float, float], b: Tuple[float, float, float], t: float) -> Tuple[float, float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _unique_points(vectors: Sequence[Tuple[float, float, float]], radius: float, cap: int) -> List[Point3D]:
    out: List[Point3D] = []
    seen = set()
    for idx, vec in enumerate(vectors):
        scaled = _norm_scale(vec, radius)
        key = (round(scaled[0], 6), round(scaled[1], 6), round(scaled[2], 6))
        if key in seen:
            continue
        seen.add(key)
        out.append(Point3D(scaled[0], scaled[1], scaled[2], idx))
        if cap and len(out) >= cap:
            break
    if cap:
        return out[:cap]
    return out


_PHI = (1.0 + math.sqrt(5.0)) / 2.0

_POLYHEDRA_DATA: Dict[str, Tuple[List[Tuple[float, float, float]], List[Tuple[int, ...]]]] = {
    "tetrahedron": (
        [
            (1, 1, 1),
            (1, -1, -1),
            (-1, 1, -1),
            (-1, -1, 1),
        ],
        [(0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)],
    ),
    "cube": (
        [
            (-1, -1, -1),
            (1, -1, -1),
            (1, 1, -1),
            (-1, 1, -1),
            (-1, -1, 1),
            (1, -1, 1),
            (1, 1, 1),
            (-1, 1, 1),
        ],
        [
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (2, 3, 7, 6),
            (1, 2, 6, 5),
            (3, 0, 4, 7),
        ],
    ),
    "octahedron": (
        [
            (1, 0, 0),
            (-1, 0, 0),
            (0, 1, 0),
            (0, -1, 0),
            (0, 0, 1),
            (0, 0, -1),
        ],
        [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)],
    ),
    "icosahedron": (
        [
            (-1, _PHI, 0),
            (1, _PHI, 0),
            (-1, -_PHI, 0),
            (1, -_PHI, 0),
            (0, -1, _PHI),
            (0, 1, _PHI),
            (0, -1, -_PHI),
            (0, 1, -_PHI),
            (_PHI, 0, -1),
            (_PHI, 0, 1),
            (-_PHI, 0, -1),
            (-_PHI, 0, 1),
        ],
        [
            (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
            (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
            (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
            (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
        ],
    ),
    "dodecahedron": (
        [
            (-1, -1, -1),
            (-1, -1, 1),
            (-1, 1, -1),
            (-1, 1, 1),
            (1, -1, -1),
            (1, -1, 1),
            (1, 1, -1),
            (1, 1, 1),
            (0, -1 / _PHI, -_PHI),
            (0, -1 / _PHI, _PHI),
            (0, 1 / _PHI, -_PHI),
            (0, 1 / _PHI, _PHI),
            (-1 / _PHI, -_PHI, 0),
            (-1 / _PHI, _PHI, 0),
            (1 / _PHI, -_PHI, 0),
            (1 / _PHI, _PHI, 0),
            (-_PHI, 0, -1 / _PHI),
            (_PHI, 0, -1 / _PHI),
            (-_PHI, 0, 1 / _PHI),
            (_PHI, 0, 1 / _PHI),
        ],
        [
            (0, 8, 10, 2, 16),
            (0, 12, 14, 4, 8),
            (0, 16, 18, 1, 12),
            (1, 9, 11, 3, 13),
            (1, 18, 19, 5, 9),
            (2, 10, 6, 17, 16),
            (2, 3, 11, 7, 6),
            (3, 13, 15, 7, 11),
            (4, 14, 15, 7, 6),
            (4, 5, 19, 17, 8),
            (5, 9, 11, 7, 15),
            (6, 7, 15, 14, 10),
        ],
    ),
}


def _polyhedron_vectors(name: str) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, ...]]]:
    data = _POLYHEDRA_DATA.get(name)
    if data:
        return data
    return ([], [])


def _polyhedron_points(
    base_vertices: Sequence[Tuple[float, float, float]],
    faces: Sequence[Tuple[int, ...]],
    radius: float,
    layers: int,
    link_steps: int,
    cap: int,
) -> List[Point3D]:
    if not base_vertices:
        return []
    vectors: List[Tuple[float, float, float]] = []
    for v in base_vertices:
        vectors.append(v)
    layers = max(1, layers)
    if layers > 1:
        for layer in range(1, layers):
            scale = layer / layers
            for v in base_vertices:
                vectors.append(_scale(v, scale))
    if link_steps > 0 and faces:
        edges = set()
        for face in faces:
            if len(face) < 2:
                continue
            for i in range(len(face)):
                a = face[i]
                b = face[(i + 1) % len(face)]
                edge = tuple(sorted((a, b)))
                edges.add(edge)
        for a, b in edges:
            va = base_vertices[a]
            vb = base_vertices[b]
            for step in range(1, link_steps + 1):
                t = step / (link_steps + 1)
                vectors.append(_mix(va, vb, t))
    return _unique_points(vectors, radius, cap)


def _parse_polyhedron_json(text: str | None) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, ...]]]:
    if not text:
        return ([], [])
    try:
        payload = json.loads(text)
    except Exception:
        return ([], [])
    vertices_raw = payload.get("vertices") if isinstance(payload, dict) else None
    faces_raw = payload.get("faces") if isinstance(payload, dict) else None
    vertices: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, ...]] = []
    if isinstance(vertices_raw, list):
        for entry in vertices_raw:
            if isinstance(entry, (list, tuple)) and len(entry) >= 3:
                try:
                    vertices.append((float(entry[0]), float(entry[1]), float(entry[2])))
                except (TypeError, ValueError):
                    continue
    if isinstance(faces_raw, list):
        for face in faces_raw:
            if isinstance(face, (list, tuple)) and len(face) >= 3:
                clean: List[int] = []
                for idx in face:
                    try:
                        clean.append(int(idx))
                    except (TypeError, ValueError):
                        continue
                if len(clean) >= 3:
                    faces.append(tuple(clean))
    return vertices, faces


def _subdivide_geodesic(level: int) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
    vertices, faces = _POLYHEDRA_DATA["icosahedron"]
    verts = [tuple(_normalize(v)) for v in vertices]
    tris = [tuple(face[:3]) for face in faces]

    def midpoint(a_idx: int, b_idx: int, cache: Dict[Tuple[int, int], int]) -> int:
        key = tuple(sorted((a_idx, b_idx)))
        cached = cache.get(key)
        if cached is not None:
            return cached
        va = verts[a_idx]
        vb = verts[b_idx]
        mid = _normalize(((va[0] + vb[0]) * 0.5, (va[1] + vb[1]) * 0.5, (va[2] + vb[2]) * 0.5))
        verts.append(mid)
        index = len(verts) - 1
        cache[key] = index
        return index

    for _ in range(max(0, level)):
        cache: Dict[Tuple[int, int], int] = {}
        new_tris: List[Tuple[int, int, int]] = []
        for a, b, c in tris:
            ab = midpoint(a, b, cache)
            bc = midpoint(b, c, cache)
            ca = midpoint(c, a, cache)
            new_tris.extend(
                [
                    (a, ab, ca),
                    (b, bc, ab),
                    (c, ca, bc),
                    (ab, bc, ca),
                ]
            )
        tris = new_tris
    return verts, tris


def _parse_spherical_terms(text: str | None) -> List[Tuple[int, int, float]]:
    if not text:
        return []
    terms: List[Tuple[int, int, float]] = []
    for token in text.replace("\r", "").split(";"):
        if not token.strip():
            continue
        parts = token.replace(",", " ").split()
        if len(parts) < 3:
            continue
        try:
            l = int(float(parts[0]))
            m = int(float(parts[1]))
            amp = float(parts[2])
        except (TypeError, ValueError):
            continue
        terms.append((max(0, l), m, amp))
    return terms


def _associated_legendre(l: int, m: int, x: float) -> float:
    m_abs = abs(m)
    pmm = 1.0
    if m_abs > 0:
        somx2 = math.sqrt(max(0.0, 1.0 - x * x))
        fact = 1.0
        for i in range(1, m_abs + 1):
            pmm *= -fact * somx2
            fact += 2.0
    if l == m_abs:
        return pmm
    pmmp1 = x * (2 * m_abs + 1) * pmm
    if l == m_abs + 1:
        return pmmp1
    pll = 0.0
    for n in range(m_abs + 2, l + 1):
        pll = ((2 * n - 1) * x * pmmp1 - (n + m_abs - 1) * pmm) / (n - m_abs)
        pmm, pmmp1 = pmmp1, pll
    return pll


def _real_spherical_harmonic(l: int, m: int, theta: float, phi: float) -> float:
    m_abs = abs(m)
    norm = math.sqrt(
        ((2 * l + 1) / (4 * math.pi))
        * (math.factorial(l - m_abs) / max(1, math.factorial(l + m_abs)))
    )
    p_lm = _associated_legendre(l, m_abs, math.cos(theta))
    if m == 0:
        return norm * p_lm
    factor = math.sqrt(2.0) * norm
    if m > 0:
        return factor * p_lm * math.cos(m * phi)
    return factor * p_lm * math.sin(m_abs * phi)


def _rand_for_index(index: int, salt: int = 0) -> float:
    s = index * 12.9898 + salt * 78.233
    x = math.sin(s) * 43758.5453
    return x - math.floor(x)


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
        self._timer.timeout.connect(self.update)
        self._timer.start(16)

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

            _draw_marker_circle(QtGui.QColor("red"), base_radius)
            _draw_marker_circle(QtGui.QColor("yellow"), base_radius * math.sqrt(1.1))
            _draw_marker_circle(QtGui.QColor("blue"), base_radius * math.sqrt(1.15))


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


def _gen_vogel_sphere_spiral(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    k = float(geo.get("vogel_k", 2.3999632) or 2.3999632)
    out: List[Point3D] = []
    for i in range(count):
        t = (i + 0.5) / count
        theta = math.acos(1.0 - 2.0 * t)
        phi = (i * k) % (2.0 * math.pi)
        sin_theta = math.sin(theta)
        out.append(
            Point3D(
                radius * sin_theta * math.cos(phi),
                radius * math.cos(theta),
                radius * sin_theta * math.sin(phi),
            )
        )
    return out


def _superquadric_coord(angle: float, exponent: float) -> float:
    exponent = max(1e-3, exponent)
    return math.copysign(abs(math.cos(angle)) ** (2.0 / exponent), math.cos(angle))


def _superquadric_sine(angle: float, exponent: float) -> float:
    exponent = max(1e-3, exponent)
    return math.copysign(abs(math.sin(angle)) ** (2.0 / exponent), math.sin(angle))


def _gen_superquadric(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    lat_steps = max(2, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    eps1 = float(geo.get("eps1", 1.0) or 1.0)
    eps2 = float(geo.get("eps2", 1.0) or 1.0)
    ax = float(geo.get("ax", 1.0) or 1.0)
    ay = float(geo.get("ay", 1.0) or 1.0)
    az = float(geo.get("az", 1.0) or 1.0)
    out: List[Point3D] = []
    for i in range(lat_steps):
        v = -0.5 * math.pi + (math.pi * i) / max(1, lat_steps - 1)
        cv = _superquadric_coord(v, eps1)
        sv = _superquadric_sine(v, eps1)
        for j in range(lon_steps):
            u = -math.pi + (2.0 * math.pi * j) / lon_steps
            cu = _superquadric_coord(u, eps2)
            su = _superquadric_sine(u, eps2)
            out.append(
                Point3D(
                    radius * ax * cv * cu,
                    radius * ay * cv * su,
                    radius * az * sv,
                )
            )
    return out[:_clamp_count(len(out), cap)]


def _gen_superellipsoid(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    lat_steps = max(2, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    ax = float(geo.get("ax", 1.0) or 1.0)
    ay = float(geo.get("ay", 1.0) or 1.0)
    az = float(geo.get("az", 1.0) or 1.0)
    n1 = float(geo.get("se_n1", 1.0) or 1.0)
    n2 = float(geo.get("se_n2", 1.0) or 1.0)
    out: List[Point3D] = []
    for i in range(lat_steps):
        v = -0.5 * math.pi + (math.pi * i) / max(1, lat_steps - 1)
        cv = math.cos(v)
        sv = math.sin(v)
        for j in range(lon_steps):
            u = -math.pi + (2.0 * math.pi * j) / lon_steps
            cu = math.cos(u)
            su = math.sin(u)
            x = radius * ax * math.copysign(abs(cv) ** (2.0 / max(1e-3, n1)), cv) * math.copysign(abs(cu) ** (2.0 / max(1e-3, n2)), cu)
            y = radius * ay * math.copysign(abs(cv) ** (2.0 / max(1e-3, n1)), cv) * math.copysign(abs(su) ** (2.0 / max(1e-3, n2)), su)
            z = radius * az * math.copysign(abs(sv) ** (2.0 / max(1e-3, n1)), sv)
            out.append(Point3D(x, y, z))
    return out[:_clamp_count(len(out), cap)]


def _gen_half_sphere(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    lat_steps = max(2, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    height = float(geo.get("half_height", 1.0) or 1.0)
    out: List[Point3D] = []
    for i in range(lat_steps):
        v = (i / max(1, lat_steps - 1)) * 0.5 * math.pi
        sin_theta = math.sin(v)
        cos_theta = math.cos(v)
        for j in range(lon_steps):
            phi = (j / lon_steps) * 2.0 * math.pi
            out.append(
                Point3D(
                    radius * sin_theta * math.cos(phi),
                    radius * cos_theta * height,
                    radius * sin_theta * math.sin(phi),
                )
            )
    return out[:_clamp_count(len(out), cap)]


def _gen_noisy_sphere(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    lat_steps = max(2, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    amp = float(geo.get("noisy_amp", 0.1) or 0.0)
    freq = float(geo.get("noisy_freq", 1.0) or 1.0)
    gain = float(geo.get("noisy_gain", 1.0) or 1.0)
    omega = float(geo.get("noisy_omega", 0.0) or 0.0)
    out: List[Point3D] = []
    for i in range(lat_steps):
        v = i / (lat_steps - 1 if lat_steps > 1 else 1)
        theta = v * math.pi
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        for j in range(lon_steps):
            u = j / lon_steps
            phi = u * 2.0 * math.pi
            nx = sin_theta * math.cos(phi)
            ny = cos_theta
            nz = sin_theta * math.sin(phi)
            n = 0.0
            frequency = freq
            amplitude = 1.0
            for _ in range(3):
                sample = _value_noise3(nx * frequency + omega, ny * frequency, nz * frequency - omega)
                n += sample * amplitude
                amplitude *= gain
                frequency *= 2.0
            offset = 1.0 + amp * (n - 0.5)
            out.append(Point3D(radius * nx * offset, radius * ny * offset, radius * nz * offset))
    return out[:_clamp_count(len(out), cap)]


def _gen_spherical_harmonics(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    lat_steps = max(2, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    terms = _parse_spherical_terms(geo.get("sph_terms"))
    out: List[Point3D] = []
    for i in range(lat_steps):
        v = i / (lat_steps - 1 if lat_steps > 1 else 1)
        theta = v * math.pi
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        for j in range(lon_steps):
            u = j / lon_steps
            phi = u * 2.0 * math.pi
            amp = 0.0
            for l, m, coeff in terms:
                amp += coeff * _real_spherical_harmonic(l, m, theta, phi)
            amp = 1.0 + amp
            amp = max(0.1, amp)
            out.append(
                Point3D(
                    radius * amp * sin_theta * math.cos(phi),
                    radius * amp * cos_theta,
                    radius * amp * sin_theta * math.sin(phi),
                )
            )
    return out[:_clamp_count(len(out), cap)]


def _gen_weighted_sphere(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    weight_expr = geo.get("weight_map")
    out: List[Point3D] = []
    for i in range(count):
        u = (i + 0.5) / count
        theta = math.acos(1 - 2 * u)
        phi = (i * 2.3999632) % (2 * math.pi)
        weight = _eval_expression(weight_expr, {"theta": theta, "phi": phi})
        weight = max(0.05, float(weight) if weight else 1.0)
        sin_theta = math.sin(theta)
        out.append(
            Point3D(
                radius * weight * sin_theta * math.cos(phi),
                radius * weight * math.cos(theta),
                radius * weight * sin_theta * math.sin(phi),
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


def _gen_horn_torus(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    horn_geo = dict(geo)
    r_minor = float(geo.get("r_minor", 0.45) or 0.45)
    horn_geo["r_minor"] = r_minor
    R_major = float(geo.get("R_major", 0.0) or r_minor)
    if not math.isfinite(R_major):
        R_major = r_minor
    # Clamp the major radius so it cannot grow beyond the minor radius.
    if R_major > r_minor:
        R_major = r_minor
    horn_geo["R_major"] = R_major
    return _gen_torus(horn_geo, cap)


def _gen_spindle_torus(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    spindle_geo = dict(geo)
    r_minor = float(geo.get("r_minor", 0.45) or 0.45)
    spindle_geo["r_minor"] = r_minor
    R_major = float(geo.get("R_major", 0.0) or (0.75 * r_minor))
    if not math.isfinite(R_major):
        R_major = 0.75 * r_minor
    # Clamp the major radius below the minor radius to keep the spindle self-intersection.
    if R_major >= r_minor:
        R_major = max(0.25 * r_minor, r_minor * 0.75)
    spindle_geo["R_major"] = R_major
    return _gen_torus(spindle_geo, cap)


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


def _gen_mobius(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    lat_steps = max(3, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    width = float(geo.get("mobius_w", 0.4) or 0.4)
    out: List[Point3D] = []
    for i in range(lat_steps):
        u = (i / lat_steps) * 2.0 * math.pi
        cos_u = math.cos(u)
        sin_u = math.sin(u)
        cos_half = math.cos(u / 2.0)
        sin_half = math.sin(u / 2.0)
        for j in range(lon_steps):
            v = (j / max(1, lon_steps - 1)) * 2.0 - 1.0
            s = v * width * 0.5
            x = (radius + s * cos_half) * cos_u
            y = (radius + s * cos_half) * sin_u
            z = s * sin_half
            out.append(Point3D(x, y, z))
    return out[:_clamp_count(len(out), cap)]


def _gen_concentric_rings(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    rings = max(1, int(geo.get("rings_count", 0) or 0))
    per_ring = max(3, int(geo.get("ring_points", 0) or 0))
    out: List[Point3D] = []
    if rings <= 1:
        out.append(Point3D(0.0, 0.0, 0.0))
    for ring in range(rings):
        r = radius * (ring / max(1, rings - 1)) if rings > 1 else 0.0
        for j in range(per_ring):
            angle = (j / per_ring) * 2.0 * math.pi
            out.append(Point3D(r * math.cos(angle), 0.0, r * math.sin(angle)))
    return out[:_clamp_count(len(out), cap)]


def _gen_hex_packing_plane(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    step = float(geo.get("hex_step", 0.2) or 0.2)
    nx = max(1, int(geo.get("hex_nx", 1) or 1))
    ny = max(1, int(geo.get("hex_ny", 1) or 1))
    points: List[Tuple[float, float]] = []
    for ix in range(nx):
        for iy in range(ny):
            x = (ix - (nx - 1) / 2.0) * step
            z = (iy - (ny - 1) / 2.0) * step * math.sqrt(3) / 2.0
            if ix % 2:
                z += step * math.sqrt(3) / 4.0
            points.append((x, z))
    max_len = max((math.hypot(x, z) for x, z in points), default=1.0) or 1.0
    scale = radius / max_len if max_len else 1.0
    out = [Point3D(x * scale, 0.0, z * scale) for x, z in points]
    return out[:_clamp_count(len(out), cap)]


def _gen_voronoi_seeds(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    count = _clamp_count(max(1, int(geo.get("voronoi_N", 0) or 0)), cap)
    xmin, xmax, ymin, ymax = _parse_bbox(geo.get("voronoi_bbox"))
    out: List[Point3D] = []
    for _ in range(count):
        x = random.uniform(xmin, xmax) * radius
        z = random.uniform(ymin, ymax) * radius
        out.append(Point3D(x, 0.0, z))
    return out


def _gen_helix(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(2, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    r = float(geo.get("helix_r", 0.4) or 0.4) * radius
    pitch = float(geo.get("helix_pitch", 0.3) or 0.3) * radius
    turns = max(0.1, float(geo.get("helix_turns", 1.0) or 1.0))
    height = pitch * turns
    out: List[Point3D] = []
    for i in range(count):
        t = turns * 2.0 * math.pi * (i / max(1, count - 1))
        x = r * math.cos(t)
        z = r * math.sin(t)
        y = -height / 2.0 + (pitch * t) / (2.0 * math.pi)
        out.append(Point3D(x, y, z))
    return out[:_clamp_count(len(out), cap)]


def _gen_viviani_curve(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(2, int(geo.get("N", 0) or 0)), cap)
    a = float(geo.get("viviani_a", 1.0) or 1.0)
    radius = float(geo.get("R", 1.0))
    out: List[Point3D] = []
    for i in range(count):
        t = 2.0 * math.pi * (i / max(1, count - 1))
        x = a * (1 + math.cos(t))
        y = a * math.sin(t)
        z = 2 * a * math.sin(t / 2.0)
        out.append(Point3D((x - 1.5 * a) * radius, y * radius, z * radius))
    return out[:_clamp_count(len(out), cap)]


def _gen_lissajous3d(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(2, int(geo.get("N", 0) or 0)), cap)
    Ax = float(geo.get("lissajous3d_Ax", 1.0) or 1.0)
    Ay = float(geo.get("lissajous3d_Ay", 1.0) or 1.0)
    Az = float(geo.get("lissajous3d_Az", 1.0) or 1.0)
    wx = max(1, int(geo.get("lissajous3d_wx", 1) or 1))
    wy = max(1, int(geo.get("lissajous3d_wy", 1) or 1))
    wz = max(1, int(geo.get("lissajous3d_wz", 1) or 1))
    phi = float(geo.get("lissajous3d_phi", 0.0) or 0.0)
    radius = float(geo.get("R", 1.0))
    out: List[Point3D] = []
    for i in range(count):
        t = 2.0 * math.pi * i / count
        x = Ax * math.sin(wx * t + phi)
        y = Ay * math.sin(wy * t)
        z = Az * math.sin(wz * t + phi / 2.0)
        out.append(Point3D(x * radius, y * radius, z * radius))
    return out[:_clamp_count(len(out), cap)]


def _gen_line_integral_convolution_sphere(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    line_count = max(1, int(geo.get("lic_N", 1) or 1))
    steps = max(4, int(geo.get("lic_steps", 0) or 0))
    out: List[Point3D] = []
    for _ in range(line_count):
        # Random great circle
        theta = random.random() * math.pi
        phi = random.random() * 2.0 * math.pi
        normal = (
            math.sin(theta) * math.cos(phi),
            math.cos(theta),
            math.sin(theta) * math.sin(phi),
        )
        ref = (0.0, 1.0, 0.0)
        if abs(sum(a * b for a, b in zip(normal, ref))) > 0.9:
            ref = (1.0, 0.0, 0.0)
        u = _normalize((
            normal[1] * ref[2] - normal[2] * ref[1],
            normal[2] * ref[0] - normal[0] * ref[2],
            normal[0] * ref[1] - normal[1] * ref[0],
        ))
        v = (
            normal[1] * u[2] - normal[2] * u[1],
            normal[2] * u[0] - normal[0] * u[2],
            normal[0] * u[1] - normal[1] * u[0],
        )
        for j in range(steps):
            angle = 2.0 * math.pi * j / steps
            point = (
                u[0] * math.cos(angle) + v[0] * math.sin(angle),
                u[1] * math.cos(angle) + v[1] * math.sin(angle),
                u[2] * math.cos(angle) + v[2] * math.sin(angle),
            )
            out.append(Point3D(point[0] * radius, point[1] * radius, point[2] * radius))
    return out[:_clamp_count(len(out), cap)]


def _gen_stream_on_torus(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    stream_count = max(1, int(geo.get("stream_N", 0) or 0))
    steps = max(8, int(geo.get("stream_steps", 0) or 0))
    R_major = float(geo.get("R_major", 1.0) or 1.0)
    r_minor = float(geo.get("r_minor", 0.3) or 0.3)
    out: List[Point3D] = []
    for i in range(stream_count):
        theta = (i / stream_count) * 2.0 * math.pi
        phi = random.random() * 2.0 * math.pi
        for j in range(steps):
            theta += 0.08
            phi += 0.12
            ring = R_major + r_minor * math.cos(theta)
            x = ring * math.cos(phi)
            y = r_minor * math.sin(theta)
            z = ring * math.sin(phi)
            out.append(Point3D(x * radius, y * radius, z * radius))
    return out[:_clamp_count(len(out), cap)]


def _gen_random_geometric_graph(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    nodes = _clamp_count(max(1, int(geo.get("rgg_nodes", 0) or 0)), cap)
    connect_radius = float(geo.get("rgg_radius", 0.2) or 0.2) * radius
    points = [
        Point3D(
            random.uniform(-radius, radius),
            random.uniform(-radius, radius) * 0.3,
            random.uniform(-radius, radius),
        )
        for _ in range(nodes)
    ]
    out = list(points)
    for i, a in enumerate(points):
        for j in range(i + 1, len(points)):
            b = points[j]
            dx = b.x - a.x
            dy = b.y - a.y
            dz = b.z - a.z
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist <= connect_radius and dist > 1e-6:
                steps = 3
                for s in range(1, steps):
                    t = s / steps
                    out.append(Point3D(a.x + dx * t, a.y + dy * t, a.z + dz * t))
    return out[:_clamp_count(len(out), cap)]


def _gen_geodesic_sphere(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    level = max(0, int(geo.get("geo_level", 0) or 0))
    vertices, _faces = _subdivide_geodesic(level)
    return _unique_points(vertices, radius, cap)


def _gen_geodesic(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    level = max(0, int(geo.get("geo_level", 0) or 0))
    vertices, faces = _subdivide_geodesic(level)
    vectors: List[Tuple[float, float, float]] = list(vertices)
    for a, b, c in faces:
        va, vb, vc = vertices[a], vertices[b], vertices[c]
        vectors.extend([_mix(va, vb, 0.5), _mix(vb, vc, 0.5), _mix(vc, va, 0.5)])
    return _unique_points(vectors, radius, cap)


def _gen_geodesic_graph(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    level = max(0, int(geo.get("geo_graph_level", 0) or 0))
    vertices, faces = _subdivide_geodesic(level)
    vectors: List[Tuple[float, float, float]] = []
    edges = set()
    for face in faces:
        for i in range(3):
            edge = tuple(sorted((face[i], face[(i + 1) % 3])))
            edges.add(edge)
    for a, b in edges:
        va, vb = vertices[a], vertices[b]
        vectors.append(va)
        vectors.append(vb)
        vectors.append(_mix(va, vb, 0.5))
    return _unique_points(vectors, radius, cap)


def _gen_polyhedron_base(name: str, geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    layers = max(1, int(geo.get("poly_layers", 0) or 0))
    link_steps = max(0, int(geo.get("poly_link_steps", 0) or 0))
    vertices, faces = _polyhedron_vectors(name)
    return _polyhedron_points(vertices, faces, radius, layers, link_steps, cap)


def _gen_tetrahedron(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    return _gen_polyhedron_base("tetrahedron", geo, cap)


def _gen_cube(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    return _gen_polyhedron_base("cube", geo, cap)


def _gen_octahedron(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    return _gen_polyhedron_base("octahedron", geo, cap)


def _gen_dodecahedron(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    return _gen_polyhedron_base("dodecahedron", geo, cap)


def _gen_icosahedron(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    return _gen_polyhedron_base("icosahedron", geo, cap)


def _gen_polyhedron(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    layers = max(1, int(geo.get("poly_layers", 0) or 0))
    link_steps = max(0, int(geo.get("poly_link_steps", 0) or 0))
    vertices, faces = _parse_polyhedron_json(geo.get("polyhedron_data"))
    if not vertices:
        vertices, faces = _polyhedron_vectors("cube")
    return _polyhedron_points(vertices, faces, radius, layers, link_steps, cap)


def _gen_truncated_icosa(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    ratio = clamp(float(geo.get("trunc_ratio", 0.333) or 0.333), 0.05, 0.45)
    base_vertices, faces = _polyhedron_vectors("icosahedron")
    vectors: List[Tuple[float, float, float]] = []
    for face in faces:
        pts = [base_vertices[idx] for idx in face[:3]]
        cx = sum(p[0] for p in pts) / 3.0
        cy = sum(p[1] for p in pts) / 3.0
        cz = sum(p[2] for p in pts) / 3.0
        for idx in face[:3]:
            v = base_vertices[idx]
            vectors.append(_mix(v, (cx, cy, cz), ratio))
    layers = max(1, int(geo.get("poly_layers", 0) or 0))
    link_steps = max(0, int(geo.get("poly_link_steps", 0) or 0))
    return _polyhedron_points(vectors, [], radius, layers, link_steps, cap)


def _gen_stellated_icosa(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    scale = float(geo.get("stellated_scale", 1.4) or 1.4)
    base_vertices, faces = _polyhedron_vectors("icosahedron")
    vectors: List[Tuple[float, float, float]] = list(base_vertices)
    for face in faces:
        pts = [base_vertices[idx] for idx in face[:3]]
        center = _normalize((
            sum(p[0] for p in pts) / 3.0,
            sum(p[1] for p in pts) / 3.0,
            sum(p[2] for p in pts) / 3.0,
        ))
        vectors.append(_scale(center, scale))
    layers = max(1, int(geo.get("poly_layers", 0) or 0))
    link_steps = max(0, int(geo.get("poly_link_steps", 0) or 0))
    return _polyhedron_points(vectors, [], radius, layers, link_steps, cap)


def _gen_blob(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    lat_steps = max(2, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    amp = float(geo.get("blob_noise_amp", 0.2) or 0.2)
    scale = float(geo.get("blob_noise_scale", 1.0) or 1.0)
    out: List[Point3D] = []
    for i in range(lat_steps):
        v = i / (lat_steps - 1 if lat_steps > 1 else 1)
        theta = v * math.pi
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        for j in range(lon_steps):
            u = j / lon_steps
            phi = u * 2.0 * math.pi
            nx = sin_theta * math.cos(phi)
            ny = cos_theta
            nz = sin_theta * math.sin(phi)
            n = _value_noise3(nx * scale, ny * scale, nz * scale)
            offset = 1.0 + amp * (n - 0.5)
            out.append(Point3D(radius * nx * offset, radius * ny * offset, radius * nz * offset))
    return out[:_clamp_count(len(out), cap)]


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


def _gen_gyroid(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    scale = float(geo.get("gyroid_scale", 1.0) or 1.0)
    thickness = float(geo.get("gyroid_thickness", 0.05) or 0.05) * radius
    c = float(geo.get("gyroid_c", 0.0) or 0.0)

    def func(x: float, y: float, z: float) -> float:
        sx = scale * x
        sy = scale * y
        sz = scale * z
        return (
            math.sin(sx) * math.cos(sy)
            + math.sin(sy) * math.cos(sz)
            + math.sin(sz) * math.cos(sx)
            - c
        )

    points = _sample_implicit_surface(count, radius, func, 0.0, thickness)
    return points[:_clamp_count(len(points), cap)]


def _gen_schwarz_P(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    scale = float(geo.get("schwarz_scale", 1.0) or 1.0)
    iso = float(geo.get("schwarz_iso", 0.0) or 0.0)
    thickness = radius * 0.03

    def func(x: float, y: float, z: float) -> float:
        sx = scale * x
        sy = scale * y
        sz = scale * z
        return math.cos(sx) + math.cos(sy) + math.cos(sz)

    points = _sample_implicit_surface(count, radius, func, iso, thickness)
    return points[:_clamp_count(len(points), cap)]


def _gen_schwarz_D(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    scale = float(geo.get("schwarz_scale", 1.0) or 1.0)
    iso = float(geo.get("schwarz_iso", 0.0) or 0.0)
    thickness = radius * 0.03

    def func(x: float, y: float, z: float) -> float:
        sx = scale * x
        sy = scale * y
        sz = scale * z
        return (
            math.sin(sx) * math.sin(sy) * math.sin(sz)
            + math.sin(sx) * math.cos(sy) * math.cos(sz)
            + math.cos(sx) * math.sin(sy) * math.cos(sz)
            + math.cos(sx) * math.cos(sy) * math.sin(sz)
        )

    points = _sample_implicit_surface(count, radius, func, iso, thickness)
    return points[:_clamp_count(len(points), cap)]


def _gen_heart_implicit(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0)) * float(geo.get("heart_scale", 1.0) or 1.0)

    def func(x: float, y: float, z: float) -> float:
        x /= radius
        y /= radius
        z /= radius
        return (
            (x * x + (9.0 / 4.0) * y * y + z * z - 1.0) ** 3
            - x * x * z * z * z
            - (9.0 / 80.0) * y * y * z * z * z
        )

    points = _sample_implicit_surface(count, radius, func, 0.0, radius * 0.02)
    return points[:_clamp_count(len(points), cap)]


def _gen_metaballs(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    centers = _parse_vector_list(geo.get("metaballs_centers"))
    radii = _parse_number_list(geo.get("metaballs_radii"))
    iso = float(geo.get("metaballs_iso", 1.0) or 1.0)
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    if not centers:
        centers = [(0.0, 0.0, 0.0)]
    if not radii:
        radii = [0.6]

    def field_value(x: float, y: float, z: float) -> float:
        total = 0.0
        for idx, center in enumerate(centers):
            rx = x - center[0]
            ry = y - center[1]
            rz = z - center[2]
            r = radii[min(idx, len(radii) - 1)]
            dist2 = rx * rx + ry * ry + rz * rz + 1e-6
            total += (r * r) / dist2
        return total

    out: List[Point3D] = []
    attempts = 0
    max_attempts = max(1000, count * 60)
    while len(out) < count and attempts < max_attempts:
        attempts += 1
        x = random.uniform(-radius, radius)
        y = random.uniform(-radius, radius)
        z = random.uniform(-radius, radius)
        val = field_value(x, y, z)
        if abs(val - iso) <= iso * 0.15:
            out.append(Point3D(x, y, z))
    return out[:_clamp_count(len(out), cap)]


def _eval_sdf(expr: str | None, x: float, y: float, z: float) -> float:
    if not expr:
        return 0.0

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


def _gen_distance_field_shape(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    expr = geo.get("df_ops")
    count = _clamp_count(max(1, int(geo.get("N", 0) or 0)), cap)
    radius = float(geo.get("R", 1.0))
    out: List[Point3D] = []
    attempts = 0
    max_attempts = max(1000, count * 60)
    while len(out) < count and attempts < max_attempts:
        attempts += 1
        x = random.uniform(-radius, radius)
        y = random.uniform(-radius, radius)
        z = random.uniform(-radius, radius)
        val = _eval_sdf(expr, x, y, z)
        if abs(val) <= radius * 0.05:
            out.append(Point3D(x, y, z))
    return out[:_clamp_count(len(out), cap)]


def _gen_superformula_3D(geo: Mapping[str, float], cap: int) -> List[Point3D]:
    radius = float(geo.get("R", 1.0))
    lat_steps = max(2, int(geo.get("lat", 0) or 0))
    lon_steps = max(3, int(geo.get("lon", 0) or 0))
    m1 = float(geo.get("sf3_m1", 0.0) or 0.0)
    m2 = float(geo.get("sf3_m2", 0.0) or 0.0)
    m3 = float(geo.get("sf3_m3", 0.0) or 0.0)
    n1 = float(geo.get("sf3_n1", 0.5) or 0.5)
    n2 = float(geo.get("sf3_n2", 0.5) or 0.5)
    n3 = float(geo.get("sf3_n3", 0.5) or 0.5)
    a = float(geo.get("sf3_a", 1.0) or 1.0)
    b = float(geo.get("sf3_b", 1.0) or 1.0)
    scale = float(geo.get("sf3_scale", 1.0) or 1.0)

    def super(theta: float, m: float) -> float:
        return _superformula2d(theta, m, a, b, n1, n2, n3)

    out: List[Point3D] = []
    for i in range(lat_steps):
        v = i / (lat_steps - 1 if lat_steps > 1 else 1)
        theta = v * math.pi - math.pi / 2.0
        r2 = super(theta, m2)
        for j in range(lon_steps):
            u = j / lon_steps
            phi = u * 2.0 * math.pi - math.pi
            r1 = super(phi, m1)
            r3 = super(phi, m3)
            x = scale * radius * r1 * r2 * math.cos(theta) * math.cos(phi)
            y = scale * radius * r1 * r2 * math.sin(theta)
            z = scale * radius * r3 * math.cos(theta) * math.sin(phi)
            out.append(Point3D(x, y, z))
    return out[:_clamp_count(len(out), cap)]
DyxtenEngine._GEOMETRY_GENERATORS = {
    "uv_sphere": _gen_uv_sphere,
    "half_sphere": _gen_half_sphere,
    "fibo_sphere": _gen_fibo_sphere,
    "vogel_sphere_spiral": _gen_vogel_sphere_spiral,
    "superquadric": _gen_superquadric,
    "superellipsoid": _gen_superellipsoid,
    "noisy_sphere": _gen_noisy_sphere,
    "spherical_harmonics": _gen_spherical_harmonics,
    "weighted_sphere": _gen_weighted_sphere,
    "disk_phyllotaxis": _gen_disk_phyllo,
    "archimede_spiral": _gen_archimede_spiral,
    "log_spiral": _gen_log_spiral,
    "rose_curve": _gen_rose_curve,
    "superformula_2D": _gen_superformula_2d,
    "density_warp_disk": _gen_density_warp,
    "poisson_disk": _gen_poisson_disk,
    "lissajous_disk": _gen_lissajous_disk,
    "concentric_rings": _gen_concentric_rings,
    "hex_packing_plane": _gen_hex_packing_plane,
    "voronoi_seeds": _gen_voronoi_seeds,
    "torus": _gen_torus,
    "double_torus": _gen_double_torus,
    "horn_torus": _gen_horn_torus,
    "spindle_torus": _gen_spindle_torus,
    "torus_knot": _gen_torus_knot,
    "mobius": _gen_mobius,
    "strip_twist": _gen_strip_twist,
    "klein_bottle": _gen_klein_bottle,
    "helix": _gen_helix,
    "lissajous3D": _gen_lissajous3d,
    "viviani_curve": _gen_viviani_curve,
    "line_integral_convolution_sphere": _gen_line_integral_convolution_sphere,
    "stream_on_torus": _gen_stream_on_torus,
    "geodesic_sphere": _gen_geodesic_sphere,
    "geodesic": _gen_geodesic,
    "geodesic_graph": _gen_geodesic_graph,
    "random_geometric_graph": _gen_random_geometric_graph,
    "tetrahedron": _gen_tetrahedron,
    "cube": _gen_cube,
    "octahedron": _gen_octahedron,
    "dodecahedron": _gen_dodecahedron,
    "icosahedron": _gen_icosahedron,
    "polyhedron": _gen_polyhedron,
    "truncated_icosa": _gen_truncated_icosa,
    "stellated_icosa": _gen_stellated_icosa,
    "blob": _gen_blob,
    "gyroid": _gen_gyroid,
    "schwarz_P": _gen_schwarz_P,
    "schwarz_D": _gen_schwarz_D,
    "heart_implicit": _gen_heart_implicit,
    "metaballs": _gen_metaballs,
    "distance_field_shape": _gen_distance_field_shape,
    "superformula_3D": _gen_superformula_3D,
}
