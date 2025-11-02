from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

__all__ = [
    "Point3D",
    "BUILTIN_GENERATORS",
    "_rand_for_index",
    "_value_noise3",
    "_scale",
    "_unique_points",
    "_PHI",
    "_gen_uv_sphere",
]


@dataclass
class Point3D:
    """Simple structure storing a 3D point and the seed used to generate it."""

    x: float
    y: float
    z: float
    seed: int = 0

    def copy(self) -> "Point3D":
        return Point3D(self.x, self.y, self.z, self.seed)

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


def _mix(a: Tuple[float, float, float], b: Tuple[float, float, float], t: float) -> Tuple[float, float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


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
            (0, 11, 5),
            (0, 5, 1),
            (0, 1, 7),
            (0, 7, 10),
            (0, 10, 11),
            (1, 5, 9),
            (5, 11, 4),
            (11, 10, 2),
            (10, 7, 6),
            (7, 1, 8),
            (3, 9, 4),
            (3, 4, 2),
            (3, 2, 6),
            (3, 6, 8),
            (3, 8, 9),
            (4, 9, 5),
            (2, 4, 11),
            (6, 2, 10),
            (8, 6, 7),
            (9, 8, 1),
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
    vectors: List[Tuple[float, float, float]] = list(base_vertices)
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
                edges.add(tuple(sorted((a, b))))
        for a, b in edges:
            try:
                va = base_vertices[a]
                vb = base_vertices[b]
            except IndexError:
                continue
            for step in range(1, link_steps + 1):
                t = step / (link_steps + 1)
                vectors.append(_mix(va, vb, t))
    points: List[Point3D] = []
    seen = set()
    for idx, vec in enumerate(vectors):
        sx = radius * float(vec[0])
        sy = radius * float(vec[1])
        sz = radius * float(vec[2])
        key = (round(sx, 6), round(sy, 6), round(sz, 6))
        if key in seen:
            continue
        seen.add(key)
        points.append(Point3D(sx, sy, sz, idx))
        if cap and len(points) >= cap:
            break
    if cap:
        return points[:cap]
    return points


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

def _polyhedron_vectors(name: str) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, ...]]]:
    data = _POLYHEDRA_DATA.get(name)
    if data:
        return data
    return ([], [])

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

BUILTIN_GENERATORS = {
    "uv_sphere": _gen_uv_sphere,
    "fibo_sphere": _gen_fibo_sphere,
    "vogel_sphere_spiral": _gen_vogel_sphere_spiral,
    "superquadric": _gen_superquadric,
    "superellipsoid": _gen_superellipsoid,
    "half_sphere": _gen_half_sphere,
    "noisy_sphere": _gen_noisy_sphere,
    "spherical_harmonics": _gen_spherical_harmonics,
    "weighted_sphere": _gen_weighted_sphere,
    "disk_phyllo": _gen_disk_phyllo,
    "disk_phyllotaxis": _gen_disk_phyllo,
    "archimede_spiral": _gen_archimede_spiral,
    "log_spiral": _gen_log_spiral,
    "rose_curve": _gen_rose_curve,
    "superformula_2d": _gen_superformula_2d,
    "superformula_2D": _gen_superformula_2d,
    "density_warp": _gen_density_warp,
    "density_warp_disk": _gen_density_warp,
    "poisson_disk": _gen_poisson_disk,
    "lissajous_disk": _gen_lissajous_disk,
    "torus": _gen_torus,
    "double_torus": _gen_double_torus,
    "horn_torus": _gen_horn_torus,
    "spindle_torus": _gen_spindle_torus,
    "torus_knot": _gen_torus_knot,
    "strip_twist": _gen_strip_twist,
    "klein_bottle": _gen_klein_bottle,
    "mobius": _gen_mobius,
    "concentric_rings": _gen_concentric_rings,
    "hex_packing_plane": _gen_hex_packing_plane,
    "voronoi_seeds": _gen_voronoi_seeds,
    "helix": _gen_helix,
    "viviani_curve": _gen_viviani_curve,
    "lissajous3d": _gen_lissajous3d,
    "lissajous3D": _gen_lissajous3d,
    "line_integral_convolution_sphere": _gen_line_integral_convolution_sphere,
    "stream_on_torus": _gen_stream_on_torus,
    "random_geometric_graph": _gen_random_geometric_graph,
    "geodesic_sphere": _gen_geodesic_sphere,
    "geodesic": _gen_geodesic,
    "geodesic_graph": _gen_geodesic_graph,
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
