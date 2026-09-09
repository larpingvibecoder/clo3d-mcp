"""Measure a CLO avatar from an OBJ export (millimetres, Y up). Pure Python, no numpy.

Materials named like "Mara:body3", "Mara:arm2", "Mara:leg2", "Mara:face2" are used; hair, eyes,
teeth, shoes and dummies are ignored. Heights are measured from the floor (min Y of the body).
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict

EXCLUDE_HINTS = ("hair", "eye", "tooth", "teeth", "lash", "shoe", "pump", "heel", "dummy", "sole", "boot",
                 "sneaker", "accessor", "glass", "brow", "sandal", "sock")


def _classify(material: str) -> str | None:
    m = material.lower()
    if any(h in m for h in EXCLUDE_HINTS):
        return None
    if "arm" in m or "hand" in m:
        return "arm"
    if "leg" in m or "foot" in m or "feet" in m:
        return "leg"
    if "face" in m or "head" in m:
        return "head"
    return "body"


def load_obj(path: str):
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, str]] = []
    current = "default"
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                p = line.split()
                verts.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("usemtl"):
                current = line[6:].strip()
            elif line.startswith("f "):
                idx = [int(t.split("/")[0]) for t in line.split()[1:]]
                idx = [i - 1 if i > 0 else len(verts) + i for i in idx]
                cls = _classify(current)
                if cls is None:
                    continue
                for k in range(1, len(idx) - 1):
                    faces.append((idx[0], idx[k], idx[k + 1], cls))
    return verts, faces


class Mesh:
    def __init__(self, verts, faces, bin_size=20.0):
        self.verts = verts
        self.faces = faces
        self.bin_size = bin_size
        self.bins: dict[int, list[int]] = defaultdict(list)
        for fi, (a, b, c, _) in enumerate(faces):
            ys = (verts[a][1], verts[b][1], verts[c][1])
            lo, hi = int(min(ys) // bin_size), int(max(ys) // bin_size)
            for bi in range(lo, hi + 1):
                self.bins[bi].append(fi)

    # ---- slicing by a horizontal plane -------------------------------------------------
    def slice_y(self, y: float, classes=("body", "leg", "arm", "head")):
        """Return closed loops (list of (x, z) polylines) of the mesh cut at height y."""
        segs = []
        for fi in self.bins.get(int(y // self.bin_size), ()):
            a, b, c, cls = self.faces[fi]
            if cls not in classes:
                continue
            pts = []
            for (p, q) in ((a, b), (b, c), (c, a)):
                pa, pb = self.verts[p], self.verts[q]
                if (pa[1] - y) * (pb[1] - y) < 0:
                    t = (y - pa[1]) / (pb[1] - pa[1])
                    pts.append((pa[0] + t * (pb[0] - pa[0]), pa[2] + t * (pb[2] - pa[2])))
                elif pa[1] == y:
                    pts.append((pa[0], pa[2]))
            if len(pts) >= 2:
                segs.append((pts[0], pts[1]))
        return _link_loops(segs)

    def slice_plane(self, origin, normal, classes=("arm",)):
        """Cut with an arbitrary plane; returns loops as 3D point lists."""
        ox, oy, oz = origin
        nx, ny, nz = normal
        segs = []
        for (a, b, c, cls) in self.faces:
            if cls not in classes:
                continue
            tri = (self.verts[a], self.verts[b], self.verts[c])
            d = [(p[0] - ox) * nx + (p[1] - oy) * ny + (p[2] - oz) * nz for p in tri]
            if max(d) < 0 or min(d) > 0:
                continue
            pts = []
            for i in range(3):
                j = (i + 1) % 3
                if d[i] * d[j] < 0:
                    t = d[i] / (d[i] - d[j])
                    pts.append(tuple(tri[i][k] + t * (tri[j][k] - tri[i][k]) for k in range(3)))
            if len(pts) >= 2:
                segs.append((pts[0], pts[1]))
        return _link_loops(segs)


def _key(p, q=0.05):
    return tuple(round(v / q) for v in p)


def _link_loops(segs):
    """Chain segments sharing endpoints into loops (open chains are returned too)."""
    if not segs:
        return []
    adj: dict = defaultdict(list)
    for i, (p, q) in enumerate(segs):
        adj[_key(p)].append((i, q))
        adj[_key(q)].append((i, p))
    used = [False] * len(segs)
    loops = []
    for i, (p, q) in enumerate(segs):
        if used[i]:
            continue
        used[i] = True
        chain = [p, q]
        cur = q
        while True:
            nxt = None
            for (j, other) in adj[_key(cur)]:
                if not used[j]:
                    nxt = (j, other)
                    break
            if nxt is None:
                break
            used[nxt[0]] = True
            cur = nxt[1]
            if _key(cur) == _key(chain[0]):
                break
            chain.append(cur)
        loops.append(chain)
    return loops


def perimeter(loop) -> float:
    n = len(loop)
    if n < 2:
        return 0.0
    total = 0.0
    for i in range(n):
        p, q = loop[i], loop[(i + 1) % n]
        total += math.dist(p, q)
    return total


def convex_hull(points):
    pts = sorted(set((round(p[0], 3), round(p[1], 3)) for p in points))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def tape(loop) -> float:
    """Tape-measure circumference: perimeter of the convex hull of a 2D loop."""
    return perimeter(convex_hull(loop))


def centroid(loop):
    n = len(loop)
    dims = len(loop[0])
    return tuple(sum(p[k] for p in loop) / n for k in range(dims))


def torso_loop(loops, max_center_offset=160.0):
    """Pick the body loop around the centre line (largest tape circumference near x=0)."""
    best = None
    for lp in loops:
        if len(lp) < 8:
            continue
        cx = centroid(lp)[0]
        if abs(cx) > max_center_offset:
            continue
        per = tape(lp)
        if best is None or per > best[0]:
            best = (per, lp)
    return best


def measure_avatar(obj_path: str, cache_dir: str | None = None, name: str | None = None) -> dict:
    """Measure body landmarks and circumferences (mm). Results are cached by avatar name."""
    if cache_dir and name:
        cache_file = os.path.join(cache_dir, f"{name}.json")
        if os.path.exists(cache_file):
            with open(cache_file) as f:
                return json.load(f)
    verts, faces = load_obj(obj_path)
    if not faces:
        raise ValueError("no body faces found in OBJ")
    mesh = Mesh(verts, faces)
    used = set()
    for a, b, c, _ in faces:
        used.add(a); used.add(b); used.add(c)
    ys = [verts[i][1] for i in used]
    floor = min(ys)
    top = max(ys)
    height = top - floor

    # facing direction: toes point forward. Compare the left foot centroid with the shin centroid.
    front_sign = 1.0
    try:
        foot = [lp for lp in mesh.slice_y(floor + 25, classes=("leg", "body")) if len(lp) > 6 and centroid(lp)[0] < 0]
        shin = [lp for lp in mesh.slice_y(floor + 160, classes=("leg", "body")) if len(lp) > 6 and centroid(lp)[0] < 0]
        if foot and shin:
            fz = centroid(max(foot, key=perimeter))[1]
            sz = centroid(max(shin, key=perimeter))[1]
            front_sign = 1.0 if fz > sz else -1.0
    except Exception:
        pass

    ALL = ("body", "leg", "arm", "head")

    def torso_perimeter(y, classes=ALL):
        loops = mesh.slice_y(y, classes=classes)
        best = torso_loop(loops)
        return (best[0], best[1]) if best else (0.0, None)

    # crotch: lowest height with a single central loop
    crotch_y = None
    y = floor + 0.30 * height
    while y < floor + 0.60 * height:
        loops = [lp for lp in mesh.slice_y(y, classes=ALL) if len(lp) > 8 and abs(centroid(lp)[0]) < 160]
        if len(loops) == 1:
            crotch_y = y
            break
        y += 8.0
    if crotch_y is None:
        crotch_y = floor + 0.45 * height

    def scan(lo, hi, step, pick, classes=ALL):
        best = None
        y = lo
        while y <= hi:
            per, lp = torso_perimeter(y, classes)
            if lp is not None and (best is None or pick(per, best[0])):
                best = (per, y, lp)
            y += step
        return best

    # shoulder tip = highest point of the arm mesh (deltoid top); armpit = lowest inner-arm point near the torso
    arm_pts = [verts[i] for (a, b, c, cls) in faces if cls == "arm" for i in (a, b, c)]
    body_pts = [verts[i] for (a, b, c, cls) in faces if cls == "body" for i in (a, b, c)]
    if arm_pts:
        shoulder_tip = max(arm_pts, key=lambda p: p[1])
    else:
        upper = [p for p in body_pts if p[1] > floor + 0.75 * height]
        shoulder_tip = max(upper, key=lambda p: abs(p[0]))
    shoulder_y = shoulder_tip[1]
    shoulder_half = abs(shoulder_tip[0])
    for dy in (5, 12, 20, 30):
        loops = [lp for lp in mesh.slice_y(shoulder_y - dy, classes=ALL) if len(lp) > 8]
        if loops:
            lp = max(loops, key=perimeter)
            half = (max(p[0] for p in lp) - min(p[0] for p in lp)) / 2.0
            shoulder_half = max(shoulder_half, half)
    inner_arm = [p for p in arm_pts if abs(p[0]) < shoulder_half + 30 and p[1] > shoulder_y - 350]
    armpit_y = min((p[1] for p in inner_arm), default=shoulder_y - 150)

    hip = scan(crotch_y + 40, crotch_y + 300, 8.0, lambda a, b: a > b)
    waist = scan(hip[1] + 80, min(hip[1] + 340, armpit_y - 150), 6.0, lambda a, b: a < b)
    # bust: most protruding front point between waist and armpit (arms are separate loops there)
    bust_best = None
    y = waist[1] + 60
    while y <= armpit_y - 15:
        per, lp = torso_perimeter(y)
        if lp is not None:
            front = max(front_sign * p[1] for p in lp)
            if bust_best is None or front > bust_best[0]:
                bust_best = (front, y, per, lp)
        y += 5.0
    if bust_best is None:
        bust_best = (0.0, waist[1] + 180, torso_perimeter(waist[1] + 180)[0], None)
    bust_y = bust_best[1]
    bust_per = bust_best[2]
    underbust = scan(max(bust_y - 120, waist[1] + 30), bust_y - 45, 5.0, lambda a, b: a < b)
    # neck base: narrowest slice above the shoulder tip
    neck = scan(shoulder_y + 5, shoulder_y + 150, 5.0, lambda a, b: a < b, classes=("body", "head", "arm"))
    neck_y = neck[1] if neck else shoulder_y + 60
    neck_per = neck[0] if neck else 360.0
    arm_info = _measure_arm(mesh, arm_pts, shoulder_tip)
    # chest/back width at armpit level (torso loop x-extent just below the armpit)
    per_ap, lp_ap = torso_perimeter(armpit_y - 25)
    chest_width = (max(p[0] for p in lp_ap) - min(p[0] for p in lp_ap)) if lp_ap else 2 * shoulder_half - 60
    # knee: narrowest left-leg loop between 20% height and the crotch
    knee = None
    y = floor + 0.20 * height
    while y < crotch_y - 80:
        loops = [lp for lp in mesh.slice_y(y, classes=("leg", "body")) if len(lp) > 8 and centroid(lp)[0] < 0]
        if loops:
            per = tape(max(loops, key=perimeter))
            if knee is None or per < knee[0]:
                knee = (per, y)
        y += 8.0
    knee_y = knee[1] if knee else floor + 0.28 * height

    result = {
        "source": os.path.basename(obj_path),
        "front_is_positive_z": front_sign > 0,
        "height": round(height, 1),
        "bust": round(bust_per, 1),
        "underbust": round(underbust[0], 1) if underbust else None,
        "waist": round(waist[0], 1),
        "hip": round(hip[0], 1),
        "neck": round(neck_per, 1),
        "shoulder_width": round(2 * shoulder_half, 1),
        "chest_width_at_armpit": round(chest_width, 1),
        "front_waist_length": round(neck_y - waist[1], 1),
        "back_waist_length": round(neck_y - waist[1], 1),
        "heights": {
            "floor": 0.0,
            "knee": round(knee_y - floor, 1),
            "crotch": round(crotch_y - floor, 1),
            "hip": round(hip[1] - floor, 1),
            "waist": round(waist[1] - floor, 1),
            "underbust": round(underbust[1] - floor, 1) if underbust else None,
            "bust": round(bust_y - floor, 1),
            "armpit": round(armpit_y - floor, 1),
            "shoulder_tip": round(shoulder_y - floor, 1),
            "neck_base": round(neck_y - floor, 1),
            "top": round(top - floor, 1),
        },
        "floor_y_world": round(floor, 2),
    }
    result.update(arm_info)
    if cache_dir and name:
        os.makedirs(cache_dir, exist_ok=True)
        with open(os.path.join(cache_dir, f"{name}.json"), "w") as f:
            json.dump(result, f, indent=1)
    return result


def _measure_arm(mesh: Mesh, arm_pts, shoulder_tip):
    """Arm length, bicep and wrist circumference from the left arm (x < 0) via plane cuts along the arm axis."""
    left = [p for p in arm_pts if p[0] < 0]
    if len(left) < 50:
        return {"arm_length": None, "bicep": None, "wrist": None}
    # arm axis: from the point nearest the shoulder tip to the farthest point (hand)
    sx, sy, sz = -abs(shoulder_tip[0]), shoulder_tip[1], shoulder_tip[2]
    far = max(left, key=lambda p: math.dist(p, (sx, sy, sz)))
    axis = (far[0] - sx, far[1] - sy, far[2] - sz)
    length = math.sqrt(sum(v * v for v in axis))
    if length < 1:
        return {"arm_length": None, "bicep": None, "wrist": None}
    n = tuple(v / length for v in axis)

    def circ_at(t):
        o = (sx + n[0] * t * length, sy + n[1] * t * length, sz + n[2] * t * length)
        loops = mesh.slice_plane(o, n, classes=("arm",))
        loops = [lp for lp in loops if len(lp) > 6 and lp[0][0] < 0]
        if not loops:
            return 0.0
        return perimeter(max(loops, key=perimeter))

    bicep = max(circ_at(t) for t in (0.14, 0.18, 0.22, 0.26, 0.30))
    wrist_candidates = [(circ_at(t), t) for t in (0.62, 0.66, 0.70, 0.74, 0.78, 0.82, 0.86)]
    wrist_candidates = [c for c in wrist_candidates if c[0] > 0]
    wrist, wrist_t = min(wrist_candidates) if wrist_candidates else (0.0, 0.8)
    return {"arm_length": round(length * wrist_t, 1), "bicep": round(bicep, 1), "wrist": round(wrist, 1)}


if __name__ == "__main__":
    import sys
    print(json.dumps(measure_avatar(sys.argv[1]), indent=1))


# ----------------------------------------------------------------------------------------------------------------
# Live scene avatar: exact measurements at arbitrary heights (used by replica recipes that need photo-exact sizing)
# ----------------------------------------------------------------------------------------------------------------
class SceneAvatar:
    """Measure the avatar mesh exported from the current CLO scene (world mm, Y up, floor = 0, shoes included).

    Unlike the cached CLO measurement table this reflects the avatar as it stands in the scene (heels, pose), so
    heights taken from it can be used directly as pattern heights."""

    def __init__(self, obj_path: str):
        verts, faces = load_obj(obj_path)
        self.mesh = Mesh(verts, faces)
        self.ymax = max(v[1] for v in verts)
        self._cache: dict = {}

    # ---- torso slices ------------------------------------------------------------------------------------------
    def torso(self, y: float):
        if y in self._cache:
            return self._cache[y]
        loops = self.mesh.slice_y(y, classes=("body",))
        t = torso_loop(loops)
        self._cache[y] = t[1] if t else None
        return self._cache[y]

    def tape(self, y: float) -> float:
        lp = self.torso(y)
        return tape(lp) if lp else 0.0

    def arcs(self, y: float):
        """(front arc, back arc, left side (x, z), right side (x, z)) of the torso hull at height y."""
        lp = self.torso(y)
        if not lp:
            return 0.0, 0.0, (0.0, 0.0), (0.0, 0.0)
        hull = convex_hull(lp)
        xs = [p[0] for p in hull]
        i, j = xs.index(max(xs)), xs.index(min(xs))
        lo, hi = min(i, j), max(i, j)
        a, b = hull[lo:hi + 1], hull[hi:] + hull[:lo + 1]
        pa = sum(math.dist(a[k], a[k + 1]) for k in range(len(a) - 1))
        pb = sum(math.dist(b[k], b[k + 1]) for k in range(len(b) - 1))
        za, zb = sum(p[1] for p in a) / len(a), sum(p[1] for p in b) / len(b)
        front, back = (pa, pb) if za > zb else (pb, pa)
        return front, back, hull[xs.index(max(xs))], hull[xs.index(min(xs))]

    def argmin_tape(self, lo: float, hi: float, step: float = 5.0) -> float:
        best = None
        y = lo
        while y <= hi:
            t = self.tape(y)
            if t and (best is None or t < best[0]):
                best = (t, y)
            y += step
        return best[1]

    def argmax_tape(self, lo: float, hi: float, step: float = 5.0) -> float:
        best = None
        y = lo
        while y <= hi:
            t = self.tape(y)
            if t and (best is None or t > best[0]):
                best = (t, y)
            y += step
        return best[1]

    def armpit_height(self, lo: float, hi: float, step: float = 5.0) -> float:
        """Lowest height at which the arm loops merge into the torso loop."""
        y = lo
        while y <= hi:
            loops = [lp for lp in self.mesh.slice_y(y, classes=("body", "arm")) if len(lp) > 8]
            if len(loops) == 1:
                return y
            y += step
        return hi

    # ---- profiles ----------------------------------------------------------------------------------------------
    def surface_z(self, x: float, y: float, side: str):
        zs = []
        for lp in self.mesh.slice_y(y, classes=("body",)):
            for k in range(len(lp)):
                p, q = lp[k], lp[(k + 1) % len(lp)]
                if (p[0] - x) * (q[0] - x) <= 0 and p[0] != q[0]:
                    t = (x - p[0]) / (q[0] - p[0])
                    zs.append(p[1] + t * (q[1] - p[1]))
        if not zs:
            return None
        return max(zs) if side == "front" else min(zs)

    def surface_length(self, x: float, y0: float, y1: float, side: str, step: float = 4.0) -> float:
        """Length of the body surface along a vertical line x = const between two heights (front or back)."""
        pts = []
        y = y0
        while y <= y1 + 1e-6:
            z = self.surface_z(x, y, side)
            if z is not None:
                pts.append((y, z))
            y += step
        return sum(math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]) for k in range(len(pts) - 1))

    def top_of_body(self, x: float, lo: float, hi: float, step: float = 3.0):
        """Highest height where the body surface still exists at |x| (shoulder slope)."""
        best = None
        y = lo
        while y <= hi:
            for lp in self.mesh.slice_y(y, classes=("body",)):
                if any(abs(p[0] - x) < step for p in lp):
                    best = y
            y += step
        return best

    def arm_tape(self, y: float, right: bool = True) -> float:
        for lp in self.mesh.slice_y(y, classes=("arm", "body")):
            if len(lp) > 8:
                cx = centroid(lp)[0]
                if (cx < -120) if right else (cx > 120):
                    return tape(lp)
        return 0.0
