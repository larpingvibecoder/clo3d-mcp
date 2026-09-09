"""Parametric garment drafting for CLO3D (pure Python, millimetres, Y up).

Conventions (verified on CLO 2026.1):
  * Pattern pieces are drawn as seen from OUTSIDE the body. A front piece's 2D +X is the wearer's LEFT,
    a back piece's 2D +X is the wearer's RIGHT. Sleeves: left sleeve 2D +X = back of the arm, right sleeve
    2D +X = front of the arm.
  * Piece Y coordinates are world heights (mm above the floor) so a piece's centre height is known.
  * Every edge starts with a corner point (type 0); intermediate points are spline points (type 2).
    CLO numbers outline lines by corner order, so line index == edge index.
  * Seam directions: an edge carries landmark tokens for its start and end. Two edges are sewn
    "forward/forward" when their start tokens match and "forward/backward" otherwise.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

Point = tuple[float, float, int]

# ----------------------------------------------------------------------------- body measurements


@dataclass
class Body:
    """Body measurements in mm. Heights are world heights above the floor."""
    height: float = 1755.0
    bust: float = 814.0
    underbust: float = 662.0
    waist: float = 608.0
    high_hip: float = 805.0
    hip: float = 953.0
    neck: float = 355.0
    armhole: float = 384.0
    bicep: float = 257.0
    elbow: float = 218.0
    wrist: float = 141.0
    thigh: float = 553.0
    knee_circ: float = 343.0
    across_shoulder: float = 377.0
    across_front: float = 324.0
    across_back: float = 319.0
    apex_width: float = 162.0
    h_hps: float = 1500.0
    h_shoulder: float = 1454.0
    h_apex: float = 1290.0
    h_underbust: float = 1235.0
    h_waist: float = 1141.0
    h_high_hip: float = 1011.0
    h_hip: float = 879.0
    h_crotch: float = 841.0
    h_knee: float = 483.0
    h_calf: float = 333.0
    h_ankle: float = 86.0
    cf_neck_waist: float = 338.0
    cb_neck_waist: float = 380.0
    arm_length: float = 589.0
    shoulder_drop: float = 46.0
    source: str = "default_female"

    @property
    def shoulder_hw(self) -> float:
        return self.across_shoulder / 2.0

    @classmethod
    def from_clo(cls, meas: dict) -> "Body":
        """Build from CLO's GetAvatarMeasurements names (values in mm)."""
        def g(name, default):
            v = meas.get(name)
            if isinstance(v, dict):
                v = v.get("value")
            return float(v) if v is not None else default
        b = cls(source="clo")
        b.height = g("HEIGHT_Total", b.height)
        b.bust = g("CIRCUMFERENCE_Bust", b.bust)
        b.underbust = g("CIRCUMFERENCE_UnderBust", b.underbust)
        b.waist = g("CIRCUMFERENCE_Waist", b.waist)
        b.high_hip = g("CIRCUMFERENCE_HighHip", b.high_hip)
        b.hip = g("CIRCUMFERENCE_LowHip", b.hip)
        b.neck = g("CIRCUMFERENCE_NeckBase", b.neck)
        b.armhole = g("CIRCUMFERENCE_Armhole", b.armhole)
        b.bicep = g("CIRCUMFERENCE_Bicep", b.bicep)
        b.elbow = g("CIRCUMFERENCE_Elbow", b.elbow)
        b.wrist = g("CIRCUMFERENCE_Wrist", b.wrist)
        b.thigh = g("CIRCUMFERENCE_Thigh", b.thigh)
        b.knee_circ = g("CIRCUMFERENCE_Knee", b.knee_circ)
        b.across_shoulder = g("LENGTH_AcrossShoulder", b.across_shoulder)
        b.across_front = g("LENGTH_AcrossFront", b.across_front)
        b.across_back = g("LENGTH_AcrossBack", b.across_back)
        b.apex_width = g("LENGTH_APEX_APEX", b.apex_width)
        b.h_hps = g("HEIGHT_HPS", b.h_hps)
        b.h_shoulder = g("HEIGHT_Shoulder", b.h_shoulder)
        b.h_apex = g("HEIGHT_APEX", b.h_apex)
        b.h_underbust = g("HEIGHT_UnderBust", b.h_underbust)
        b.h_waist = g("HEIGHT_Waist", b.h_waist)
        b.h_high_hip = g("HEIGHT_HighHip", b.h_high_hip)
        b.h_hip = g("HEIGHT_LowHip", b.h_hip)
        b.h_crotch = g("HEIGHT_Crotch", b.h_crotch)
        b.h_knee = g("HEIGHT_Knee", b.h_knee)
        b.h_calf = g("HEIGHT_Calf", b.h_calf)
        b.h_ankle = g("HEIGHT_Ankle", b.h_ankle)
        b.cf_neck_waist = g("LENGTH_CFNeck_Waist", b.cf_neck_waist)
        b.cb_neck_waist = g("LENGTH_CBNeck_Waist", b.cb_neck_waist)
        b.arm_length = g("LENGTH_Arm", b.arm_length)
        b.shoulder_drop = g("HEIGHT_ShoulderDrop", b.shoulder_drop)
        return b

    @classmethod
    def from_obj_measure(cls, m: dict) -> "Body":
        b = cls(source="obj")
        h = m.get("heights", {})
        b.height = m.get("height", b.height)
        b.bust = m.get("bust") or b.bust
        b.underbust = m.get("underbust") or b.underbust
        b.waist = m.get("waist") or b.waist
        b.hip = m.get("hip") or b.hip
        b.neck = m.get("neck") or b.neck
        b.bicep = m.get("bicep") or b.bicep
        b.wrist = m.get("wrist") or b.wrist
        b.across_shoulder = m.get("shoulder_width") or b.across_shoulder
        b.arm_length = m.get("arm_length") or b.arm_length
        b.h_knee = h.get("knee") or b.h_knee
        b.h_crotch = h.get("crotch") or b.h_crotch
        b.h_hip = h.get("hip") or b.h_hip
        b.h_waist = h.get("waist") or b.h_waist
        b.h_apex = h.get("bust") or b.h_apex
        b.h_underbust = h.get("underbust") or b.h_underbust
        b.h_shoulder = h.get("shoulder_tip") or b.h_shoulder
        b.h_hps = h.get("neck_base") or b.h_hps
        return b


# ----------------------------------------------------------------------------- geometry helpers


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def polyline_length(pts) -> float:
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def curve(p0, p1, bulge: float, n: int = 3, profile=None):
    """Intermediate spline points (type 2) between p0 and p1, offset perpendicular to the chord.
    bulge > 0 pushes the points to the left of the direction p0->p1 (y-up coordinates)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    out = []
    for i in range(1, n + 1):
        t = i / (n + 1)
        w = profile(t) if profile else math.sin(math.pi * t)
        x, y = lerp(p0, p1, t)
        out.append((x + nx * bulge * w, y + ny * bulge * w, 2))
    return out


def bulge_toward(p0, p1, target_x: float, amount: float) -> float:
    """Signed bulge so that the curve bends toward x=target_x."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1.0
    nx = -dy / L
    mid_x = (p0[0] + p1[0]) / 2
    return amount if (target_x - mid_x) * nx > 0 else -amount


def arc_points(cx, cy, r, a0_deg, a1_deg, n_inner: int):
    """Spline points along an arc (excluding the two end points)."""
    out = []
    for i in range(1, n_inner + 1):
        t = i / (n_inner + 1)
        a = math.radians(a0_deg + (a1_deg - a0_deg) * t)
        out.append((cx + r * math.cos(a), cy + r * math.sin(a), 2))
    return out


def arc_end(cx, cy, r, a_deg):
    a = math.radians(a_deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


# ----------------------------------------------------------------------------- pieces & plan


@dataclass
class Edge:
    name: str
    start: str            # landmark token at the first point
    end: str              # landmark token at the last point (= next edge's first point)
    pts: list             # [(x, y, type)] ; pts[0] is the corner (type 0)

    def length(self, next_corner) -> float:
        return polyline_length([(p[0], p[1]) for p in self.pts] + [next_corner])


@dataclass
class Piece:
    name: str
    role: str                         # bodice_front, bodice_back, skirt_front, skirt_back, sleeve_L, sleeve_R, strap_L, strap_R ...
    edges: list = field(default_factory=list)
    arrangement: str = ""             # arrangement point name
    x_percent: int = 50
    offset_mm: int = 30
    fabric: str = "main"
    elastic: dict = field(default_factory=dict)   # edge name -> total length mm (gathers the edge)
    layout_dx: float = 0.0            # 2D placement offset
    layout_dy: float = 0.0
    layer: int = 0                    # CLO layer (stacked pieces such as tiers)

    # --- derived
    def polygon(self) -> list:
        pts = []
        for e in self.edges:
            pts.extend(e.pts)
        return pts

    def corners(self) -> list:
        return [(e.pts[0][0], e.pts[0][1]) for e in self.edges]

    def edge_index(self, name: str) -> int:
        for i, e in enumerate(self.edges):
            if e.name == name:
                return i
        raise KeyError(f"{self.name}: no edge {name!r} (have {[e.name for e in self.edges]})")

    def edge_length(self, name: str) -> float:
        i = self.edge_index(name)
        nxt = self.edges[(i + 1) % len(self.edges)].pts[0]
        return self.edges[i].length((nxt[0], nxt[1]))

    def bbox(self):
        pts = self.polygon()
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def centre_height(self) -> float:
        _, y0, _, y1 = self.bbox()
        return (y0 + y1) / 2

    def height(self) -> float:
        _, y0, _, y1 = self.bbox()
        return y1 - y0

    def world_points(self) -> list:
        """Polygon with the 2D layout offset applied (this is what is sent to CLO)."""
        return [(round(p[0] + self.layout_dx, 2), round(p[1] + self.layout_dy, 2), p[2]) for p in self.polygon()]


@dataclass
class Seam:
    piece_a: str
    edge_a: str
    piece_b: str
    edge_b: str
    flip: bool | None = None      # None -> derived from landmark tokens
    gather: bool = False          # intentional length mismatch (gathers)
    note: str = ""


@dataclass
class Plan:
    pieces: list = field(default_factory=list)
    seams: list = field(default_factory=list)
    fabric: dict = field(default_factory=dict)
    simulation: dict = field(default_factory=lambda: {"steps": 120, "particle_distance": 20})
    body: Body | None = None
    spec: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    merge_pairs: list = field(default_factory=list)   # [(base_piece, piece_to_merge)] joined after simulation

    def piece(self, name: str) -> Piece:
        for p in self.pieces:
            if p.name == name:
                return p
        raise KeyError(name)

    def resolve_seams(self) -> list:
        """Return seams as dicts with piece names, line indices and CLO direction flags."""
        out = []
        for s in self.seams:
            pa, pb = self.piece(s.piece_a), self.piece(s.piece_b)
            ia, ib = pa.edge_index(s.edge_a), pb.edge_index(s.edge_b)
            ea, eb = pa.edges[ia], pb.edges[ib]
            flip = s.flip
            if flip is None:
                if ea.start == eb.start and ea.end == eb.end:
                    flip = False
                elif ea.start == eb.end and ea.end == eb.start:
                    flip = True
                else:
                    flip = False
                    self.warnings.append(f"seam {s.piece_a}.{s.edge_a} <-> {s.piece_b}.{s.edge_b}: landmark tokens do not match "
                                         f"({ea.start}->{ea.end} vs {eb.start}->{eb.end}); assuming same direction")
            la, lb = pa.edge_length(s.edge_a), pb.edge_length(s.edge_b)
            ratio = (max(la, lb) / min(la, lb)) if min(la, lb) > 0 else 99
            if not s.gather and ratio > 1.08:
                self.warnings.append(f"seam {s.piece_a}.{s.edge_a} ({la:.0f}mm) <-> {s.piece_b}.{s.edge_b} ({lb:.0f}mm) differs by {100*(ratio-1):.0f}%")
            out.append({"piece_a": s.piece_a, "line_a": ia, "piece_b": s.piece_b, "line_b": ib,
                        "dir_a": True, "dir_b": (not flip), "len_a": round(la, 1), "len_b": round(lb, 1),
                        "gather": s.gather, "note": s.note})
        return out

    def to_dict(self) -> dict:
        return {
            "pieces": [{
                "name": p.name, "role": p.role, "points": p.world_points(),
                "edges": [{"name": e.name, "line": i, "length": round(p.edge_length(e.name), 1)} for i, e in enumerate(p.edges)],
                "arrangement": p.arrangement, "x_percent": p.x_percent, "offset_mm": p.offset_mm,
                "centre_height": round(p.centre_height(), 1), "height": round(p.height(), 1),
                "fabric": p.fabric, "layer": p.layer,
                "elastic": [{"line": p.edge_index(k), "total_length": v} for k, v in p.elastic.items()],
            } for p in self.pieces],
            "seams": self.resolve_seams(),
            "fabric": self.fabric,
            "simulation": self.simulation,
            "warnings": self.warnings,
            "notes": self.notes,
            "merge_pairs": self.merge_pairs,
            "spec": self.spec,
        }


# ----------------------------------------------------------------------------- style tables

EASE = {  # (bust, waist, hip) total ease in mm
    "bodycon": (0.0, -10.0, 0.0),
    "fitted": (40.0, 30.0, 40.0),
    "regular": (80.0, 70.0, 80.0),
    "loose": (150.0, 140.0, 140.0),
    "oversized": (260.0, 260.0, 240.0),
}

NECKLINES = {  # front: (depth below HPS, extra half width)
    "round": (85.0, 5.0), "crew": (70.0, 0.0), "scoop": (135.0, 10.0), "v": (170.0, 5.0), "deep-v": (250.0, 8.0),
    "square": (130.0, 25.0), "sweetheart": (150.0, 30.0), "boat": (40.0, 55.0), "high": (35.0, 0.0),
    "off-shoulder": (200.0, 90.0), "halter": (120.0, -20.0),
}
BACK_NECKLINES = {"round": 25.0, "scoop": 90.0, "v": 150.0, "deep-v": 260.0, "open": 330.0, "high": 15.0, "square": 60.0}

SLEEVE_LENGTHS = {"cap": 70.0, "short": 220.0, "elbow": 330.0, "three-quarter": 440.0, "long": None, "bracelet": None}

COLOR_NAMES = {
    "black": (0.05, 0.05, 0.05), "white": (0.96, 0.96, 0.96), "ivory": (0.95, 0.92, 0.84), "cream": (0.96, 0.93, 0.86),
    "red": (0.78, 0.08, 0.12), "crimson": (0.7, 0.05, 0.15), "burgundy": (0.45, 0.06, 0.14), "wine": (0.4, 0.08, 0.16),
    "pink": (0.95, 0.6, 0.72), "blush": (0.93, 0.76, 0.75), "hot pink": (0.92, 0.2, 0.55), "fuchsia": (0.85, 0.1, 0.5),
    "coral": (0.98, 0.5, 0.45), "orange": (0.95, 0.5, 0.12), "peach": (0.98, 0.8, 0.65), "yellow": (0.98, 0.85, 0.2),
    "mustard": (0.85, 0.65, 0.13), "gold": (0.83, 0.68, 0.22), "green": (0.15, 0.5, 0.25), "emerald": (0.02, 0.55, 0.35),
    "sage": (0.6, 0.7, 0.55), "olive": (0.45, 0.48, 0.2), "mint": (0.6, 0.9, 0.75), "forest": (0.05, 0.3, 0.15),
    "teal": (0.05, 0.45, 0.5), "turquoise": (0.2, 0.75, 0.75), "blue": (0.15, 0.3, 0.75), "navy": (0.1, 0.16, 0.42),
    "royal blue": (0.15, 0.25, 0.8), "sky blue": (0.55, 0.75, 0.95), "baby blue": (0.65, 0.8, 0.95), "cobalt": (0.0, 0.28, 0.67),
    "purple": (0.45, 0.2, 0.6), "lavender": (0.75, 0.68, 0.9), "lilac": (0.78, 0.65, 0.85), "violet": (0.5, 0.25, 0.75),
    "plum": (0.5, 0.15, 0.35), "brown": (0.4, 0.25, 0.15), "chocolate": (0.3, 0.17, 0.1), "tan": (0.8, 0.65, 0.45),
    "beige": (0.85, 0.78, 0.65), "camel": (0.76, 0.6, 0.42), "khaki": (0.7, 0.65, 0.45), "grey": (0.5, 0.5, 0.5),
    "gray": (0.5, 0.5, 0.5), "charcoal": (0.2, 0.2, 0.22), "silver": (0.75, 0.75, 0.78), "nude": (0.87, 0.72, 0.6),
    "champagne": (0.95, 0.87, 0.72), "rose": (0.85, 0.45, 0.55), "magenta": (0.8, 0.1, 0.6), "cyan": (0.1, 0.7, 0.8),
}

FABRIC_KEYWORDS = [  # (keywords, library file stem)
    (("satin", "silk", "charmeuse", "duchess"), "V2_Woven_Satin_1"),
    (("chiffon",), "V2_Woven_Chiffon_1"),
    (("georgette",), "V2_Woven_Georgette_1"),
    (("crepe", "cdc", "crepe de chine"), "V2_Woven_Crepe_CDC_1"),
    (("organza",), "V2_Woven_Organza_1"),
    (("taffeta",), "V2_Woven_Taffeta_1"),
    (("tulle", "mesh", "net"), "V2_Cut_Sew_Knit_Mesh_Tulle_1"),
    (("lace",), "V2_Cut_Sew_Knit_Lace_1"),
    (("velvet", "velveteen"), "V2_Woven_Velvet_Velveteen_1"),
    (("velour",), "V2_Cut_Sew_Knit_Velour_1"),
    (("jersey", "t-shirt", "tee", "knit", "stretch"), "V2_Cut_Sew_Knit_Jersey_1"),
    (("ity", "matte jersey", "slinky"), "V2_Cut_Sew_Knit_ITY_MatteJersey_1"),
    (("ponte", "double knit"), "V2_Cut_Sew_Knit_Ponte_1"),
    (("scuba", "neoprene"), "V2_Cut_Sew_Knit_Neoprene_Scuba_1"),
    (("rib", "ribbed"), "V2_Cut_Sew_Knit_Rib_1"),
    (("crepe knit",), "V2_Cut_Sew_Knit_CrepeKnit_1"),
    (("denim", "jean"), "V2_Woven_Denim_1"),
    (("chambray", "oxford"), "V2_Woven_Chambray_Oxford_1"),
    (("poplin", "cotton", "shirting"), "V2_Woven_Poplin_1"),
    (("linen", "plain weave"), "V2_Woven_Plain_1"),
    (("twill", "gabardine"), "V2_Woven_Twill_1"),
    (("canvas", "duck"), "V2_Woven_Canvas_1"),
    (("wool", "suiting", "tweed"), "V2_Woven_Tweed_1"),
    (("melton", "boiled wool", "coating"), "V2_Woven_Melton_Boiled_1"),
    (("flannel",), "V2_Woven_Flannel_1"),
    (("voile", "lawn"), "V2_Woven_Voile_1"),
    (("gauze", "double gauze", "muslin"), "V2_Woven_Gauze_DoubleGauze_1"),
    (("challis", "rayon", "viscose"), "V2_Woven_Challis_1"),
    (("seersucker",), "V2_Woven_Seersucker_1"),
    (("corduroy", "cord"), "V2_Woven_Corduroy_1"),
    (("jacquard", "brocade", "damask"), "V2_Woven_Jacquard_Brocade_1"),
    (("boucle",), "V2_Woven_Boucle_1"),
    (("plaid", "tartan", "check"), "V2_Woven_Plaid_1"),
    (("eyelet", "broderie"), "V2_Woven_Eyelet_1"),
    (("dobby",), "V2_Woven_Dobby_1"),
    (("leather",), "V2_Leather_Full_Grain"),
    (("vegan leather", "pleather", "pu"), "V2_Animal_Alternatives_VeganLeather_1"),
    (("suede",), "V2_Animal_Alternatives_VeganSuede_1"),
    (("fur",), "V2_Animal_Alternatives_VeganFur_1"),
    (("fleece",), "V2_Cut_Sew_Knit_Fleece_1"),
    (("french terry", "sweatshirt"), "V2_Cut_Sew_Knit_FrenchTerry_1"),
    (("pique", "polo"), "V2_Cut_Sew_Knit_Pique_1"),
    (("interlock",), "V2_Cut_Sew_Knit_DoubleKnit_Interlock_1"),
    (("ripstop", "nylon"), "V2_Woven_Ripstop_1"),
    (("crochet",), "V2_Cut_Sew_Knit_Crochet_1"),
    (("pointelle",), "V2_Cut_Sew_Knit_Pointelle_1"),
    (("waffle",), "V2_Cut_Sew_Knit_Waffle_1"),
    (("sherpa",), "V2_Cut_Sew_Knit_Sherpa_1"),
    (("ottoman",), "V2_Woven_Ottoman_1"),
    (("dewspo", "sportswear"), "V2_Woven_Dewspo_1"),
]


def fabric_file_for(keyword: str | None) -> tuple[str, str]:
    """Return (library file stem, matched keyword) for a free-text fabric description."""
    if not keyword:
        return "V2_Woven_Crepe_CDC_1", "default (crepe)"
    k = keyword.lower().strip()
    if k.endswith(".zfab"):
        return keyword, "path"
    best = None
    for keys, stem in FABRIC_KEYWORDS:
        for kw in keys:
            if kw in k and (best is None or len(kw) > len(best[1])):
                best = (stem, kw)
    return best if best else ("V2_Woven_Crepe_CDC_1", "default (crepe)")


def parse_color(color) -> tuple[float, float, float]:
    if color is None:
        return (0.85, 0.85, 0.85)
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        vals = [float(v) for v in color[:3]]
        return tuple(v / 255.0 if max(vals) > 1.0 else v for v in vals)
    s = str(color).strip().lower()
    if s.startswith("#") and len(s) in (7, 4):
        if len(s) == 4:
            s = "#" + "".join(ch * 2 for ch in s[1:])
        return tuple(int(s[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
    # longest matching colour name in the text
    best = None
    for name, rgb in COLOR_NAMES.items():
        if name in s and (best is None or len(name) > len(best[0])):
            best = (name, rgb)
    if best:
        return best[1]
    return (0.85, 0.85, 0.85)


# ----------------------------------------------------------------------------- drafting blocks


def hem_height(body: Body, length, garment: str = "dress") -> float:
    """World height of the hem for a length keyword or a number (mm above floor if > 40, else metres)."""
    if isinstance(length, (int, float)):
        v = float(length)
        return v * 1000 if v < 40 else v
    k = (length or "knee").lower().replace("_", "-")
    table = {
        "micro": body.h_crotch + 60, "mini": body.h_knee + 190, "above-knee": body.h_knee + 90, "above the knee": body.h_knee + 90,
        "knee": body.h_knee - 15, "below-knee": body.h_knee - 90, "midi": (body.h_knee + body.h_ankle) / 2 + 20,
        "tea": body.h_ankle + 160, "tea-length": body.h_ankle + 160, "ankle": body.h_ankle + 30, "maxi": body.h_ankle + 15,
        "floor": 12.0, "floor-length": 12.0,
        # tops
        "cropped": body.h_waist + 60, "waist": body.h_waist - 15, "hip": body.h_high_hip - 20, "tunic": body.h_hip - 60,
    }
    if garment == "top" and k not in table:
        return body.h_high_hip - 20
    return table.get(k, body.h_knee - 15)


def neckline_front_edge(kind: str, hps: float, snp_r, snp_l, extra_depth: float = 0.0) -> Edge:
    """Neckline edge from SNP_R (2D left) to SNP_L (2D right), passing below HPS by the neckline depth."""
    depth, _ = NECKLINES.get(kind, NECKLINES["round"])
    depth += extra_depth
    y = hps - depth
    xr, xl = snp_r[0], snp_l[0]
    if kind in ("v", "deep-v", "halter"):
        pts = [(xr, snp_r[1], 0), (0.0, y, 0)]
        # two straight lines: a corner at CF makes the neckline two lines; that is fine (no seam here)
        return Edge("neckline", "snp_R", "snp_L", pts)
    if kind == "square":
        return Edge("neckline", "snp_R", "snp_L", [(xr, snp_r[1], 0), (xr, y, 0), (xl, y, 0)])
    if kind == "sweetheart":
        pts = [(xr, snp_r[1], 0), (xr - 5, y + 45, 2), (xr * 0.5, y - 5, 2), (0.0, y + 35, 0),
               (xl * 0.5, y - 5, 2), (xl + 5, y + 45, 2)]
        return Edge("neckline", "snp_R", "snp_L", pts)
    # round family: smooth U through spline points
    w = xl  # half width (positive)
    pts = [(xr, snp_r[1], 0),
           (-w * 0.92, hps - depth * 0.45, 2),
           (-w * 0.6, hps - depth * 0.86, 2),
           (0.0, y, 2),
           (w * 0.6, hps - depth * 0.86, 2),
           (w * 0.92, hps - depth * 0.45, 2)]
    return Edge("neckline", "snp_R", "snp_L", pts)


def neckline_back_edge(kind: str, hps: float, snp_l, snp_r) -> Edge:
    """Back neckline from SNP_L (2D left on the back piece) to SNP_R (2D right)."""
    depth = BACK_NECKLINES.get(kind, 25.0)
    y = hps - depth
    xl, xr = snp_l[0], snp_r[0]
    w = xr
    if kind in ("v", "deep-v"):
        return Edge("neckline", "snp_L", "snp_R", [(xl, snp_l[1], 0), (0.0, y, 0)])
    if kind == "square":
        return Edge("neckline", "snp_L", "snp_R", [(xl, snp_l[1], 0), (xl, y, 0), (xr, y, 0)])
    if kind == "open":
        return Edge("neckline", "snp_L", "snp_R", [(xl, snp_l[1], 0), (-w * 0.85, hps - depth * 0.5, 2), (0.0, y, 2), (w * 0.85, hps - depth * 0.5, 2)])
    pts = [(xl, snp_l[1], 0), (-w * 0.6, hps - depth * 0.85, 2), (0.0, y, 2), (w * 0.6, hps - depth * 0.85, 2)]
    return Edge("neckline", "snp_L", "snp_R", pts)


def armhole_edge(name: str, start_tok: str, end_tok: str, p_top, p_bottom, downward: bool) -> Edge:
    """Armhole curve between the shoulder tip and the underarm point, bending toward the body centre."""
    p0, p1 = (p_top, p_bottom) if downward else (p_bottom, p_top)
    amount = 22.0 + 0.12 * abs(p_bottom[1] - p_top[1])
    b = bulge_toward(p0, p1, 0.0, amount)
    # more curvature near the underarm: asymmetric profile
    prof = (lambda t: math.sin(math.pi * t) * (0.55 + 0.9 * t)) if downward else (lambda t: math.sin(math.pi * t) * (0.55 + 0.9 * (1 - t)))
    pts = [(p0[0], p0[1], 0)] + curve(p0, p1, b, n=3, profile=prof)
    return Edge(name, start_tok, end_tok, pts)


def side_edge(name: str, start_tok: str, end_tok: str, stations: list, downward: bool) -> Edge:
    """Side seam through (x, y) stations; first and last are corners, the rest spline points."""
    st = stations if downward else list(reversed(stations))
    pts = [(st[0][0], st[0][1], 0)] + [(x, y, 2) for (x, y) in st[1:-1]]
    return Edge(name, start_tok, end_tok, pts)


def curved_hem_edge(name: str, start_tok: str, end_tok: str, waist_hw: float, waist_h: float, hem_hw: float, hem_h: float, front: bool) -> tuple[Edge, float]:
    """Hem edge for a flared panel: the side corners are raised so the side seam length equals the centre length,
    and the hem runs along a smooth arc through the centre-bottom point. Returns (edge, side corner height)."""
    length = waist_h - hem_h
    spread = hem_hw - waist_hw
    dy = math.sqrt(max(length * length - spread * spread, (length * 0.5) ** 2))
    side_h = waist_h - (length - 0.7 * (length - dy))   # raise the side corners most of the way to a level hem
    # arc through (hem_hw, side_h), (0, hem_h), (-hem_hw, side_h): spline points
    pts = [(hem_hw, side_h, 0)]
    for t in (0.25, 0.5, 0.75):
        x = hem_hw * (1 - 2 * t)
        # parabola-like blend between side height and centre height
        y = side_h + (hem_h - side_h) * (1 - (2 * t - 1) ** 2)
        pts.append((x, y, 2))
    return Edge(name, start_tok, end_tok, pts), side_h


def _ease(fit: str):
    return EASE.get(fit, EASE["regular"])


def bodice_piece(body: Body, spec: dict, side: str, bottom_h: float, one_piece_hem_hw: float | None = None,
                 strapless: bool = False, straps: bool = False, bottom_token: str = "hem", split_bottom: bool = False) -> Piece:
    """Front or back bodice (or one-piece dress body) as a full symmetric piece."""
    fit = spec.get("fit", "regular")
    eb, ew, eh = _ease(fit)
    ex = spec.get("ease", {}) if isinstance(spec.get("ease"), dict) else {}
    eb, ew, eh = ex.get("bust", eb), ex.get("waist", ew), ex.get("hip", eh)
    front = side == "front"
    bal = 8.0 if front else -8.0                      # front/back balance
    bust_hw = (body.bust + eb) / 4 + bal
    waist_hw = (body.waist + ew) / 4 + bal * 0.5
    hip_hw = (body.hip + eh) / 4 + bal * 0.5
    neck_hw = body.neck / 6 + 8
    shoulder_hw = body.shoulder_hw
    hps = body.h_hps
    st_h = hps - body.shoulder_drop
    underarm_h = body.h_apex + 25.0 if fit != "oversized" else body.h_apex - 15.0
    if straps or strapless:
        top_h = body.h_apex + (40.0 if front else 60.0)
    kind_f = spec.get("neckline", "round")
    kind_b = spec.get("back_neckline", "round")
    _, extra_w = NECKLINES.get(kind_f, NECKLINES["round"])
    neck_hw_f = min(neck_hw + extra_w, shoulder_hw - 85.0)   # keep at least 85 mm of shoulder seam so the bodice stays up
    neck_hw_b = neck_hw_f

    # side seam stations from the underarm down
    stations = [(bust_hw, underarm_h)]
    if bottom_h >= body.h_waist - 5:            # bodice ends at (or above) the waist
        if bottom_h < body.h_underbust:
            stations.append((waist_hw + (bust_hw - waist_hw) * 0.35, body.h_underbust))
        stations.append((waist_hw if bottom_h <= body.h_waist + 5 else waist_hw + (bust_hw - waist_hw) * 0.5, bottom_h))
        bottom_hw = stations[-1][0]
    else:                                        # one-piece: through waist and hip to the hem
        stations.append((waist_hw, body.h_waist))
        stations.append((hip_hw, body.h_hip))
        hem_hw = one_piece_hem_hw if one_piece_hem_hw is not None else hip_hw
        if bottom_h < body.h_hip - 20:
            stations.append((hem_hw, bottom_h))
        else:
            stations[-1] = (hem_hw, bottom_h)
        bottom_hw = hem_hw

    if front:
        # 2D +x = wearer's left. Clockwise from SNP_L.
        snp_l = (neck_hw_f, hps)
        snp_r = (-neck_hw_f, hps)
        st_l = (shoulder_hw, st_h)
        st_r = (-shoulder_hw, st_h)
        edges = []
        if straps:
            sw = 22.0 if (spec.get("straps") or "thin") == "thin" else 45.0
            sx = neck_hw + 55.0                      # strap centre distance from CF
            sy = hps - body.shoulder_drop * (sx / shoulder_hw) - 8.0   # shoulder line height at the strap
            top_l = (bust_hw - 6, top_h)
            top_r = (-(bust_hw - 6), top_h)
            # clockwise: right strap (2D -x) first: top_R -> strap outer -> up -> shoulder -> down -> inner ... -> left strap
            edges.append(Edge("top_R_out", "top_R", "spR_out_b", [(top_r[0], top_r[1], 0)]))
            edges.append(Edge("strap_R_out", "spR_out_b", "spR_out_t", [(-(sx + sw / 2), top_h, 0)]))
            edges.append(Edge("shoulder_R", "st_R", "snp_R", [(-(sx + sw / 2), sy, 0)]))       # sewn to the back strap top
            edges.append(Edge("strap_R_in", "spR_in_t", "spR_in_b", [(-(sx - sw / 2), sy, 0)]))
            mid = [(-(sx - sw / 2), top_h, 0)]
            if kind_f == "sweetheart":
                mid += [(-(sx - sw / 2) * 0.5, top_h - 10, 2), (0.0, top_h + 22, 2), ((sx - sw / 2) * 0.5, top_h - 10, 2)]
            edges.append(Edge("top", "spR_in_b", "spL_in_b", mid))
            edges.append(Edge("strap_L_in", "spL_in_b", "spL_in_t", [((sx - sw / 2), top_h, 0)]))
            edges.append(Edge("shoulder_L", "snp_L", "st_L", [((sx - sw / 2), sy, 0)]))
            edges.append(Edge("strap_L_out", "spL_out_t", "spL_out_b", [((sx + sw / 2), sy, 0)]))
            edges.append(Edge("top_L_out", "spL_out_b", "top_L", [((sx + sw / 2), top_h, 0)]))
            edges.append(Edge("top_side_L", "top_L", "ua_L", [(top_l[0], top_l[1], 0)]))
        elif strapless:
            top_l = (bust_hw - 6, top_h)
            top_r = (-(bust_hw - 6), top_h)
            edges.append(Edge("top", "top_R", "top_L", [(top_r[0], top_r[1], 0)] +
                              ([( -bust_hw * 0.45, top_h - 12, 2), (0.0, top_h + 18, 2), (bust_hw * 0.45, top_h - 12, 2)]
                               if kind_f == "sweetheart" else [])))
            edges.append(Edge("top_side_L", "top_L", "ua_L", [(top_l[0], top_l[1], 0)]))
        else:
            edges.append(Edge("shoulder_L", "snp_L", "st_L", [(snp_l[0], snp_l[1], 0)]))
            edges.append(armhole_edge("armhole_L", "st_L", "ua_L", st_l, (bust_hw, underarm_h), downward=True))
        bt = bottom_token
        flared = (bottom_h < body.h_hip - 60) and (bottom_hw > hip_hw + 25)
        if flared:
            hem_edge, side_h = curved_hem_edge("hem", f"{bt}_L", f"{bt}_R", hip_hw, body.h_hip, bottom_hw, bottom_h, True)
            stations[-1] = (bottom_hw, side_h)
        edges.append(side_edge("side_L", "ua_L", f"{bt}_L", [(x, y) for x, y in stations], downward=True))
        if split_bottom:
            edges.append(Edge("hem_L_half", f"{bt}_L", "cf", [(bottom_hw, bottom_h, 0)]))
            edges.append(Edge("hem_R_half", "cf", f"{bt}_R", [(0.0, bottom_h, 0)]))
        elif flared:
            edges.append(hem_edge)
        else:
            edges.append(Edge("hem", f"{bt}_L", f"{bt}_R", [(bottom_hw, bottom_h, 0)]))
        edges.append(side_edge("side_R", f"{bt}_R", "ua_R", [(-x, y) for x, y in stations], downward=False))
        if straps or strapless:
            edges.append(Edge("top_side_R", "ua_R", "top_R", [(-bust_hw, underarm_h, 0)]))
        else:
            edges.append(armhole_edge("armhole_R", "ua_R", "st_R", st_r, (-bust_hw, underarm_h), downward=False))
            edges.append(Edge("shoulder_R", "st_R", "snp_R", [(st_r[0], st_r[1], 0)]))
            edges.append(neckline_front_edge(kind_f, hps, snp_r, snp_l))
        piece = Piece("Front", "bodice_front", edges, layout_dx=-520.0)
    else:
        # back: 2D +x = wearer's right. Clockwise from SNP_R.
        snp_r = (neck_hw_b, hps)
        snp_l = (-neck_hw_b, hps)
        st_r = (shoulder_hw, st_h)
        st_l = (-shoulder_hw, st_h)
        edges = []
        if straps:
            sw = 22.0 if (spec.get("straps") or "thin") == "thin" else 45.0
            sx = neck_hw + 55.0
            sy = hps - body.shoulder_drop * (sx / shoulder_hw) - 8.0
            top_r = (bust_hw - 6, top_h)
            top_l = (-(bust_hw - 6), top_h)
            # clockwise from top-left (wearer's left strap is on 2D -x for the back piece)
            edges.append(Edge("top_L_out", "top_L", "spL_out_b", [(top_l[0], top_l[1], 0)]))
            edges.append(Edge("strap_L_out", "spL_out_b", "spL_out_t", [(-(sx + sw / 2), top_h, 0)]))
            edges.append(Edge("shoulder_L", "st_L", "snp_L", [(-(sx + sw / 2), sy, 0)]))
            edges.append(Edge("strap_L_in", "spL_in_t", "spL_in_b", [(-(sx - sw / 2), sy, 0)]))
            edges.append(Edge("top", "spL_in_b", "spR_in_b", [(-(sx - sw / 2), top_h, 0)]))
            edges.append(Edge("strap_R_in", "spR_in_b", "spR_in_t", [((sx - sw / 2), top_h, 0)]))
            edges.append(Edge("shoulder_R", "snp_R", "st_R", [((sx - sw / 2), sy, 0)]))
            edges.append(Edge("strap_R_out", "spR_out_t", "spR_out_b", [((sx + sw / 2), sy, 0)]))
            edges.append(Edge("top_R_out", "spR_out_b", "top_R", [((sx + sw / 2), top_h, 0)]))
            edges.append(Edge("top_side_R", "top_R", "ua_R", [(top_r[0], top_r[1], 0)]))
        elif strapless:
            top_r = (bust_hw - 6, top_h)
            top_l = (-(bust_hw - 6), top_h)
            edges.append(Edge("top", "top_L", "top_R", [(top_l[0], top_l[1], 0)]))
            edges.append(Edge("top_side_R", "top_R", "ua_R", [(top_r[0], top_r[1], 0)]))
        else:
            edges.append(Edge("shoulder_R", "snp_R", "st_R", [(snp_r[0], snp_r[1], 0)]))
            edges.append(armhole_edge("armhole_R", "st_R", "ua_R", st_r, (bust_hw, underarm_h), downward=True))
        bt = bottom_token
        flared = (bottom_h < body.h_hip - 60) and (bottom_hw > hip_hw + 25)
        if flared:
            hem_edge, side_h = curved_hem_edge("hem", f"{bt}_R", f"{bt}_L", hip_hw, body.h_hip, bottom_hw, bottom_h, False)
            stations[-1] = (bottom_hw, side_h)
        edges.append(side_edge("side_R", "ua_R", f"{bt}_R", [(x, y) for x, y in stations], downward=True))
        if split_bottom:
            edges.append(Edge("hem_R_half", f"{bt}_R", "cb", [(bottom_hw, bottom_h, 0)]))
            edges.append(Edge("hem_L_half", "cb", f"{bt}_L", [(0.0, bottom_h, 0)]))
        elif flared:
            edges.append(hem_edge)
        else:
            edges.append(Edge("hem", f"{bt}_R", f"{bt}_L", [(bottom_hw, bottom_h, 0)]))
        edges.append(side_edge("side_L", f"{bt}_L", "ua_L", [(-x, y) for x, y in stations], downward=False))
        if straps or strapless:
            edges.append(Edge("top_side_L", "ua_L", "top_L", [(-bust_hw, underarm_h, 0)]))
        else:
            edges.append(armhole_edge("armhole_L", "ua_L", "st_L", st_l, (-bust_hw, underarm_h), downward=False))
            edges.append(Edge("shoulder_L", "st_L", "snp_L", [(st_l[0], st_l[1], 0)]))
            edges.append(neckline_back_edge(kind_b, hps, snp_l, snp_r))
        piece = Piece("Back", "bodice_back", edges, layout_dx=520.0)
    piece.meta_underarm_h = underarm_h  # type: ignore[attr-defined]
    return piece


def skirt_pieces(body: Body, spec: dict, waist_h: float, hem_h: float, bodice_waist_len: float | None) -> tuple[list, list]:
    """Return ([pieces], [seams]) for the requested skirt type, hung from waist_h."""
    kind = (spec.get("skirt") or "a-line").lower().replace("_", "-")
    fit = spec.get("fit", "regular")
    _, ew, eh = _ease(fit)
    length = waist_h - hem_h
    waist_total = body.waist + max(ew, 20.0)
    if waist_h < body.h_waist - 40:          # drop waist: hang from the high hip circumference
        waist_total = body.high_hip + max(ew, 20.0)
    elif waist_h > body.h_underbust - 30:    # empire
        waist_total = body.underbust + max(ew, 30.0)
    if bodice_waist_len:
        waist_total = 2 * bodice_waist_len
    hip_total = body.hip + eh
    pieces, seams = [], []

    def panel(name, role, waist_hw, hip_hw, hem_hw, dx, front):
        # clockwise trapezoid; front 2D +x = wearer's left ; back 2D +x = wearer's right
        L, R = ("L", "R") if front else ("R", "L")   # token for the 2D +x side
        flared = hem_hw > hip_hw + 25
        if flared:
            hem_edge, side_h = curved_hem_edge("hem", f"hem_{L}", f"hem_{R}", waist_hw, waist_h, hem_hw, hem_h, front)
        else:
            hem_edge, side_h = Edge("hem", f"hem_{L}", f"hem_{R}", [(hem_hw, hem_h, 0)]), hem_h
        stations = [(waist_hw, waist_h)]
        if length > 200 and body.h_hip < waist_h - 40 and hem_h < body.h_hip - 30:
            stations.append((hip_hw, body.h_hip))
        stations.append((hem_hw, side_h))
        edges = [
            Edge("waist", f"waist_{R}", f"waist_{L}", [(-waist_hw, waist_h, 0)]),
            side_edge(f"side_{L}", f"waist_{L}", f"hem_{L}", stations, downward=True),
            hem_edge,
            side_edge(f"side_{R}", f"hem_{R}", f"waist_{R}", [(-x, y) for x, y in stations], downward=False),
        ]
        return Piece(name, role, edges, layout_dx=dx)

    if kind in ("straight", "pencil", "column", "a-line", "flare", "flared", "trumpet", "mermaid", "tulip"):
        waist_hw = waist_total / 4
        hip_hw = hip_total / 4
        flare = {"straight": 0.02, "pencil": -0.05, "column": 0.0, "a-line": 0.32, "flare": 0.6, "flared": 0.6,
                 "trumpet": 0.5, "mermaid": 0.55, "tulip": 0.15}[kind]
        hem_hw = max(hip_hw + flare * length * 0.5, hip_hw * 0.8)
        if kind in ("mermaid", "trumpet"):
            # fitted to the knee then flared
            knee_hw = (body.knee_circ * 2 + 80) / 4 + 20
            def mer_panel(name, role, dx, front):
                L, R = ("L", "R") if front else ("R", "L")
                stations = [(waist_hw, waist_h), (hip_hw, body.h_hip), (knee_hw, body.h_knee + 40), (knee_hw + 20, body.h_knee - 60), (hem_hw + 60, hem_h)]
                edges = [Edge("waist", f"waist_{R}", f"waist_{L}", [(-waist_hw, waist_h, 0)]),
                         side_edge(f"side_{L}", f"waist_{L}", f"hem_{L}", stations, downward=True),
                         Edge("hem", f"hem_{L}", f"hem_{R}", [(stations[-1][0], hem_h, 0)]),
                         side_edge(f"side_{R}", f"hem_{R}", f"waist_{R}", [(-x, y) for x, y in stations], downward=False)]
                return Piece(name, role, edges, layout_dx=dx)
            pieces = [mer_panel("Skirt_Front", "skirt_front", -520.0, True), mer_panel("Skirt_Back", "skirt_back", 520.0, False)]
        else:
            pieces = [panel("Skirt_Front", "skirt_front", waist_hw, hip_hw, hem_hw, -520.0, True),
                      panel("Skirt_Back", "skirt_back", waist_hw, hip_hw, hem_hw, 520.0, False)]
        seams = [Seam("Skirt_Front", "side_L", "Skirt_Back", "side_L"), Seam("Skirt_Front", "side_R", "Skirt_Back", "side_R")]
    elif kind in ("gathered", "dirndl", "full", "pleated", "tiered"):
        ratio = float(spec.get("gather_ratio", 1.8 if kind != "tiered" else 1.35))
        if kind == "tiered":
            tiers = int(spec.get("tiers", 3))
            tier_h = length / tiers
            prev_hw = waist_total / 4
            for i in range(tiers):
                top_h = waist_h - i * tier_h
                bot_h = waist_h - (i + 1) * tier_h
                hw = prev_hw * ratio if i > 0 else waist_total / 4 * ratio
                for front in (True, False):
                    L, R = ("L", "R") if front else ("R", "L")
                    name = f"Tier{i+1}_{'Front' if front else 'Back'}"
                    edges = [Edge("waist", f"t{i}_{R}", f"t{i}_{L}", [(-hw, top_h, 0)]),
                             Edge(f"side_{L}", f"t{i}_{L}", f"b{i}_{L}", [(hw, top_h, 0)]),
                             Edge("hem", f"b{i}_{L}", f"b{i}_{R}", [(hw, bot_h, 0)]),
                             Edge(f"side_{R}", f"b{i}_{R}", f"t{i}_{R}", [(-hw, bot_h, 0)])]
                    pieces.append(Piece(name, "skirt_front" if front else "skirt_back", edges, layout_dx=-520.0 if front else 520.0, layer=i))
                seams.append(Seam(f"Tier{i+1}_Front", "side_L", f"Tier{i+1}_Back", "side_L"))
                seams.append(Seam(f"Tier{i+1}_Front", "side_R", f"Tier{i+1}_Back", "side_R"))
                if i > 0:
                    seams.append(Seam(f"Tier{i}_Front", "hem", f"Tier{i+1}_Front", "waist", gather=True, flip=True))
                    seams.append(Seam(f"Tier{i}_Back", "hem", f"Tier{i+1}_Back", "waist", gather=True, flip=True))
                prev_hw = hw
        else:
            hw = waist_total / 4 * ratio
            for front in (True, False):
                L, R = ("L", "R") if front else ("R", "L")
                name = "Skirt_Front" if front else "Skirt_Back"
                edges = [Edge("waist", f"waist_{R}", f"waist_{L}", [(-hw, waist_h, 0)]),
                         Edge(f"side_{L}", f"waist_{L}", f"hem_{L}", [(hw, waist_h, 0)]),
                         Edge("hem", f"hem_{L}", f"hem_{R}", [(hw, hem_h, 0)]),
                         Edge(f"side_{R}", f"hem_{R}", f"waist_{R}", [(-hw, hem_h, 0)])]
                pieces.append(Piece(name, "skirt_front" if front else "skirt_back", edges, layout_dx=-520.0 if front else 520.0))
            seams = [Seam("Skirt_Front", "side_L", "Skirt_Back", "side_L"), Seam("Skirt_Front", "side_R", "Skirt_Back", "side_R")]
    elif kind in ("half-circle", "full-circle", "circle", "quarter-circle", "three-quarter-circle"):
        fraction = {"half-circle": 0.5, "full-circle": 1.0, "circle": 1.0, "quarter-circle": 0.25, "three-quarter-circle": 0.75}[kind]
        # four panels (front L/R, back L/R), each a sector of angle 360*fraction/4 with waist arc = waist_total/4
        sector = 360.0 * fraction / 4.0
        r_w = (waist_total / 4.0) / math.radians(sector)
        r_h = r_w + length
        half = sector / 2.0
        for front in (True, False):
            for wearer_side in ("R", "L"):
                # 2D placement: the panel's bisector points down (waist arc at the top, centre of the circle above)
                # panel spans angles [-90-half, -90+half] measured from the circle centre placed at (0, waist_h + r_w)
                cy = waist_h + r_w
                a0, a1 = -90.0 - half, -90.0 + half
                # decide which 2D side is the centre front/back and which is the side seam
                # front piece: 2D +x = wearer's left ; a piece for wearer_side R has its CF at 2D +x (toward wearer's left)
                if front:
                    cf_on_plus_x = (wearer_side == "R")
                else:
                    cf_on_plus_x = (wearer_side == "L")
                tok_side = wearer_side
                tok_centre = "cf" if front else "cb"
                left_tok = tok_centre if not cf_on_plus_x else tok_side
                right_tok = tok_side if not cf_on_plus_x else tok_centre
                w0 = arc_end(0, cy, r_w, a0)  # left end of waist arc (2D -x)
                w1 = arc_end(0, cy, r_w, a1)
                h0 = arc_end(0, cy, r_h, a0)
                h1 = arc_end(0, cy, r_h, a1)
                n_w = max(3, int(sector / 12))
                def wt(t):
                    return t if t in ("cf", "cb") else f"waist_{t}"
                def ht(t):
                    return f"hem_{t}"
                edges = [
                    Edge("waist", wt(left_tok), wt(right_tok), [(w0[0], w0[1], 0)] + arc_points(0, cy, r_w, a0, a1, n_w)),
                    Edge("edge_right", wt(right_tok), ht(right_tok), [(w1[0], w1[1], 0)]),
                    Edge("hem", ht(right_tok), ht(left_tok), [(h1[0], h1[1], 0)] + arc_points(0, cy, r_h, a1, a0, n_w * 2)),
                    Edge("edge_left", ht(left_tok), wt(left_tok), [(h0[0], h0[1], 0)]),
                ]
                name = f"Skirt_{'Front' if front else 'Back'}_{wearer_side}"
                dx = (-1 if front else 1) * (300 + r_h * 0.5) * (1 if cf_on_plus_x else 1)
                # spread the four panels in 2D
                dx = {("F", "R"): -900, ("F", "L"): -300, ("B", "L"): 300, ("B", "R"): 900}[("F" if front else "B", wearer_side)]
                p = Piece(name, "skirt_front" if front else "skirt_back", edges, layout_dx=float(dx))
                p.circle_edges = {"centre": "edge_right" if cf_on_plus_x else "edge_left", "side": "edge_left" if cf_on_plus_x else "edge_right"}  # type: ignore[attr-defined]
                pieces.append(p)
        def pc(front, side):
            return f"Skirt_{'Front' if front else 'Back'}_{side}"
        def ce(name, which):
            return next(p for p in pieces if p.name == name).circle_edges[which]  # type: ignore[attr-defined]
        seams = [
            Seam(pc(True, "R"), ce(pc(True, "R"), "centre"), pc(True, "L"), ce(pc(True, "L"), "centre")),
            Seam(pc(False, "R"), ce(pc(False, "R"), "centre"), pc(False, "L"), ce(pc(False, "L"), "centre")),
            Seam(pc(True, "L"), ce(pc(True, "L"), "side"), pc(False, "L"), ce(pc(False, "L"), "side")),
            Seam(pc(True, "R"), ce(pc(True, "R"), "side"), pc(False, "R"), ce(pc(False, "R"), "side")),
        ]
    else:
        raise ValueError(f"unknown skirt type {kind!r}")
    return pieces, seams


def lower_body_pieces(body: Body, waist_hw_front: float, waist_hw_back: float, hip_hw: float, hem_hw: float,
                      waist_h: float, hem_h: float) -> list:
    """Waist-to-hem pieces of a one-piece dress (sewn to the bodice at the waist, merged after simulation)."""
    pieces = []
    for front, whw in ((True, waist_hw_front), (False, waist_hw_back)):
        L, R = ("L", "R") if front else ("R", "L")
        stations = [(whw, waist_h)]
        if hem_h < body.h_hip - 30:
            stations.append((hip_hw, body.h_hip))
        flared = hem_hw > hip_hw + 25 and hem_h < body.h_hip - 60
        if flared:
            hem_edge, side_h = curved_hem_edge("hem", f"hem_{L}", f"hem_{R}", hip_hw, body.h_hip, hem_hw, hem_h, front)
        else:
            hem_edge, side_h = Edge("hem", f"hem_{L}", f"hem_{R}", [(hem_hw, hem_h, 0)]), hem_h
        stations.append((hem_hw, side_h))
        edges = [
            Edge("waist", f"waist_{R}", f"waist_{L}", [(-whw, waist_h, 0)]),
            side_edge(f"side_{L}", f"waist_{L}", f"hem_{L}", stations, downward=True),
            hem_edge,
            side_edge(f"side_{R}", f"hem_{R}", f"waist_{R}", [(-x, y) for x, y in stations], downward=False),
        ]
        pieces.append(Piece("Lower_Front" if front else "Lower_Back", "skirt_front" if front else "skirt_back", edges,
                            layout_dx=-520.0 if front else 520.0))
    return pieces


def sleeve_piece(body: Body, spec: dict, side: str, armhole_len: float, underarm_h: float, shoulder_h: float) -> Piece:
    """Set-in sleeve. side 'L' or 'R'. 2D +x = back of the arm for L, front of the arm for R."""
    style = (spec.get("sleeve_style") or "regular").lower()
    length_key = (spec.get("sleeve") or "short").lower().replace("_", "-")
    fit = spec.get("fit", "regular")
    bicep_ease = {"fitted": 30.0, "regular": 55.0, "puff": 170.0, "bishop": 120.0, "flutter": 60.0, "bell": 60.0, "balloon": 200.0}.get(style, 55.0)
    if fit in ("loose", "oversized"):
        bicep_ease += 40.0
    width = body.bicep + bicep_ease
    total_len = SLEEVE_LENGTHS.get(length_key)
    if total_len is None:
        total_len = body.arm_length + (15.0 if length_key == "long" else -60.0)
    cap_ease = 12.0 if style in ("fitted", "regular") else 60.0 if style == "puff" else 25.0
    target = armhole_len + cap_ease
    if style in ("puff", "balloon"):
        target = armhole_len * 1.45

    def cap_curves(cap_h):
        xw = width / 2
        y0 = shoulder_h - cap_h                      # bicep line height in the piece's own frame
        top = (0.0, shoulder_h)
        back_ua = (xw, y0)
        front_ua = (-xw, y0)
        # classic S-curve: below the diagonal near the underarm, above it near the top
        def s_pts(p_from, p_to, k_low, k_high):
            out = []
            for t in (0.25, 0.5, 0.75):
                x, y = lerp(p_from, p_to, t)
                bump = -k_low * math.sin(math.pi * t) if t < 0.5 else k_high * math.sin(math.pi * t)
                dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
                L = math.hypot(dx, dy)
                nx, ny = -dy / L, dx / L
                out.append((x + nx * bump, y + ny * bump, 2))
            return out
        front_pts = [(front_ua[0], front_ua[1], 0)] + s_pts(front_ua, top, -cap_h * 0.16, cap_h * 0.22)
        back_pts = [(top[0], top[1], 0)] + s_pts(top, back_ua, cap_h * 0.18, -cap_h * 0.10)
        f_len = polyline_length([(p[0], p[1]) for p in front_pts] + [top])
        b_len = polyline_length([(p[0], p[1]) for p in back_pts] + [back_ua])
        return front_pts, back_pts, f_len + b_len, y0

    cap_h = max(80.0, armhole_len * 0.30)
    for _ in range(25):
        f, b, L, y0 = cap_curves(cap_h)
        if abs(L - target) < 2.0:
            break
        cap_h *= (target / L) ** 1.4 if L > 0 else 1.0
        cap_h = max(50.0, min(cap_h, width * 0.9))
    front_pts, back_pts, cap_len, y0 = cap_curves(cap_h)
    total_len = max(total_len, cap_h + 55.0)
    hem_h = shoulder_h - total_len
    xw = width / 2
    if style == "fitted" and length_key in ("long", "bracelet"):
        hem_hw = (body.wrist + 70.0) / 2
    elif length_key in ("long", "bracelet"):
        hem_hw = (body.wrist + 110.0) / 2
    elif style in ("flutter", "bell"):
        hem_hw = xw + total_len * 0.35
    elif style in ("puff", "balloon", "bishop"):
        hem_hw = xw * 0.95
    else:
        hem_hw = xw * 0.9 if total_len > 250 else xw * 0.96
    L = side
    if side == "L":
        # 2D -x = front of arm, +x = back of arm. Clockwise from front underarm.
        edges = [
            Edge("cap_front", f"ua_{L}", f"st_{L}", front_pts),
            Edge("cap_back", f"st_{L}", f"ua_{L}", back_pts),
            Edge("underarm_back", f"sl_ua_{L}", f"sl_hem_{L}", [(xw, y0, 0)]),
            Edge("hem", f"sl_hem_{L}", f"sl_hem2_{L}", [(hem_hw, hem_h, 0)]),
            Edge("underarm_front", f"sl_hem2_{L}", f"sl_ua_{L}", [(-hem_hw, hem_h, 0)]),
        ]
        # underarm_back starts at the back underarm corner (which is also cap_back's end)
        edges[2].start = f"sl_ua_{L}"
        dx = -1300.0
    else:
        # right sleeve: 2D +x = front of arm. Mirror the x coordinates of the left sleeve.
        def mirror(pts):
            return [(-p[0], p[1], p[2]) for p in pts]
        back_m = mirror(back_pts)   # runs from top to (−xw) i.e. the back underarm now on 2D -x ... reverse to keep clockwise
        # clockwise order for the mirrored piece: start at back underarm (2D -x), cap_back up to top, cap_front down to front ua (2D +x)
        cap_back_rev = [( -xw, y0, 0)] + [(-p[0], p[1], 2) for p in reversed(back_pts[1:])]
        cap_front_rev = [(0.0, shoulder_h, 0)] + [(-p[0], p[1], 2) for p in reversed(front_pts[1:])]
        edges = [
            Edge("cap_back", f"ua_{L}", f"st_{L}", cap_back_rev),
            Edge("cap_front", f"st_{L}", f"ua_{L}", cap_front_rev),
            Edge("underarm_front", f"sl_ua_{L}", f"sl_hem_{L}", [(xw, y0, 0)]),
            Edge("hem", f"sl_hem_{L}", f"sl_hem2_{L}", [(hem_hw, hem_h, 0)]),
            Edge("underarm_back", f"sl_hem2_{L}", f"sl_ua_{L}", [(-hem_hw, hem_h, 0)]),
        ]
        dx = 1300.0
    piece = Piece(f"Sleeve_{side}", f"sleeve_{side}", edges, layout_dx=dx)
    piece.arrangement = f"Arm_Outside_2_{side}"
    if style in ("puff", "balloon", "bishop"):
        piece.elastic["hem"] = body.bicep + 40.0 if total_len < 300 else body.wrist + 60.0
    piece.cap_len = cap_len  # type: ignore[attr-defined]
    return piece


def strap_pieces(body: Body, spec: dict, front: Piece, back: Piece) -> tuple[list, list]:
    width = 22.0 if (spec.get("straps") or "thin") == "thin" else 45.0
    # strap runs over the shoulder from the front top edge to the back top edge
    top_f = front.edges[front.edge_index("top")].pts[0][1]
    top_b = back.edges[back.edge_index("top")].pts[0][1]
    length = (body.h_hps - top_f) + (body.h_hps - top_b) + 2 * 55.0
    pieces, seams = [], []
    for side, dx in (("L", -1200.0), ("R", 1200.0)):
        y_top = body.h_hps + 40
        edges = [
            Edge("top", f"strap_top_{side}_a", f"strap_top_{side}_b", [(-width / 2, y_top, 0)]),
            Edge("side_a", f"strap_top_{side}_b", f"strap_bot_{side}_b", [(width / 2, y_top, 0)]),
            Edge("bottom", f"strap_bot_{side}_b", f"strap_bot_{side}_a", [(width / 2, y_top - length, 0)]),
            Edge("side_b", f"strap_bot_{side}_a", f"strap_top_{side}_a", [(-width / 2, y_top - length, 0)]),
        ]
        p = Piece(f"Strap_{side}", f"strap_{side}", edges, layout_dx=dx)
        p.arrangement = f"Shoulder_{side}"
        pieces.append(p)
    return pieces, seams


# ----------------------------------------------------------------------------- spec -> plan


SILHOUETTES = {
    # name: dict(one_piece, skirt, fit, hem_flare, waist)
    "sheath": {"one_piece": True, "fit": "fitted", "flare": -0.03},
    "pencil": {"one_piece": True, "fit": "fitted", "flare": -0.05},
    "bodycon": {"one_piece": True, "fit": "bodycon", "flare": -0.04},
    "shift": {"one_piece": True, "fit": "regular", "flare": 0.05},
    "a-line": {"one_piece": True, "fit": "regular", "flare": 0.30},
    "tent": {"one_piece": True, "fit": "loose", "flare": 0.55},
    "trapeze": {"one_piece": True, "fit": "loose", "flare": 0.55},
    "slip": {"one_piece": True, "fit": "fitted", "flare": 0.08, "straps": "thin", "neckline": "straight"},
    "strapless": {"one_piece": True, "fit": "fitted", "flare": 0.05, "strapless": True},
    "tube": {"one_piece": True, "fit": "bodycon", "flare": -0.02, "strapless": True},
    "mermaid": {"one_piece": False, "skirt": "mermaid", "fit": "fitted"},
    "fit-and-flare": {"one_piece": False, "skirt": "flare", "fit": "fitted"},
    "skater": {"one_piece": False, "skirt": "full-circle", "fit": "fitted"},
    "fit and flare": {"one_piece": False, "skirt": "flare", "fit": "fitted"},
    "empire": {"one_piece": False, "skirt": "gathered", "fit": "fitted", "waist": "empire"},
    "babydoll": {"one_piece": False, "skirt": "gathered", "fit": "regular", "waist": "empire"},
    "ball gown": {"one_piece": False, "skirt": "full-circle", "fit": "fitted"},
    "ballgown": {"one_piece": False, "skirt": "full-circle", "fit": "fitted"},
    "princess": {"one_piece": False, "skirt": "full-circle", "fit": "fitted"},
    "circle": {"one_piece": False, "skirt": "full-circle", "fit": "fitted"},
    "gathered": {"one_piece": False, "skirt": "gathered", "fit": "fitted"},
    "dirndl": {"one_piece": False, "skirt": "gathered", "fit": "fitted"},
    "tiered": {"one_piece": False, "skirt": "tiered", "fit": "regular"},
    "drop-waist": {"one_piece": False, "skirt": "gathered", "fit": "regular", "waist": "drop"},
    "shirt": {"one_piece": True, "fit": "loose", "flare": 0.15},
    "shirt-dress": {"one_piece": True, "fit": "loose", "flare": 0.15},
    "wrap": {"one_piece": False, "skirt": "a-line", "fit": "fitted"},
    "smock": {"one_piece": False, "skirt": "gathered", "fit": "loose", "waist": "empire"},
    "peplum": {"one_piece": False, "skirt": "flare", "fit": "fitted"},
}


def normalize_spec(spec: dict) -> dict:
    s = {k.lower().replace(" ", "_"): v for k, v in (spec or {}).items()}
    s.setdefault("garment", "dress")
    s["garment"] = str(s["garment"]).lower()
    sil = str(s.get("silhouette") or ("a-line" if s["garment"] == "dress" else "regular")).lower().replace("_", "-")
    s["silhouette"] = sil
    if s["garment"] == "dress":
        preset = SILHOUETTES.get(sil) or SILHOUETTES.get(sil.replace("-", " ")) or SILHOUETTES["a-line"]
        for k, v in preset.items():
            s.setdefault(k, v)
        if s.get("skirt") and "one_piece" not in s:
            s["one_piece"] = False
    elif s["garment"] == "skirt":
        s.setdefault("skirt", sil if sil in ("a-line", "straight", "pencil", "flare", "gathered", "half-circle", "full-circle", "tiered", "mermaid") else "a-line")
    else:  # top
        s.setdefault("one_piece", True)
        s.setdefault("flare", 0.05)
    s.setdefault("fit", "regular")
    s.setdefault("neckline", "round")
    s.setdefault("back_neckline", "round" if s["neckline"] not in ("deep-v", "halter") else "v")
    s.setdefault("sleeve", "none")
    s.setdefault("sleeve_style", "regular")
    s.setdefault("waist", "natural")
    s.setdefault("length", "knee" if s["garment"] != "top" else "hip")
    s.setdefault("straps", "none")
    s.setdefault("strapless", False)
    if s["neckline"] in ("straight", "strapless") and s["straps"] == "none":
        s["strapless"] = True
    if s["silhouette"] == "slip":
        s["straps"] = s.get("straps") or "thin"
        if s["straps"] == "none":
            s["straps"] = "thin"
    if s.get("straps") not in (None, "none"):
        s["sleeve"] = "none"
    return s


def plan_garment(spec: dict, body: Body) -> Plan:
    s = normalize_spec(spec)
    plan = Plan(body=body, spec=s)
    garment = s["garment"]
    hem_h = hem_height(body, s.get("length"), garment)
    straps = s.get("straps") not in (None, "none")
    strapless = bool(s.get("strapless")) and not straps
    has_sleeves = s.get("sleeve", "none") != "none" and not straps and not strapless

    waist_key = s.get("waist", "natural")
    waist_h = {"natural": body.h_waist, "empire": body.h_underbust - 10.0, "drop": body.h_high_hip + 10.0,
               "high": body.h_waist + 40.0, "none": body.h_waist}.get(waist_key, body.h_waist)

    if garment == "skirt":
        skirts, sk_seams = skirt_pieces(body, s, waist_h, hem_h, None)
        plan.pieces.extend(skirts)
        plan.seams.extend(sk_seams)
        kind = (s.get("skirt") or "a-line").lower().replace("_", "-")
        n_waist_pieces = sum(1 for p in skirts if p.name.startswith("Tier1") or (kind != "tiered" and p.role.startswith("skirt")))
        for p in skirts:
            at_waist = p.name.startswith("Tier1") or (kind != "tiered" and p.role.startswith("skirt"))
            if at_waist and "waist" in [e.name for e in p.edges]:
                p.elastic["waist"] = (waist_total_for_elastic := (body.waist - 25.0)) / max(1, n_waist_pieces)
        plan.notes.append("standalone skirt: the waist edge is held by elastic so it stays on the body")
    else:
        one_piece = bool(s.get("one_piece", True))
        bottom_h = hem_h if one_piece else waist_h
        flare = float(s.get("flare", 0.0))
        eb, ew, eh = _ease(s.get("fit", "regular"))
        hip_hw = (body.hip + eh) / 4
        drop = max(0.0, body.h_hip - hem_h)
        hem_hw = hip_hw + flare * drop * 0.5 if one_piece else None
        if one_piece and s.get("silhouette") in ("pencil", "bodycon") and hem_h < body.h_knee + 30:
            hem_hw = hip_hw - 6.0
        elif one_piece and s.get("silhouette") == "sheath":
            hem_hw = hip_hw + 8.0
        kind = (s.get("skirt") or "a-line").lower().replace("_", "-")
        circle = (not one_piece) and kind in ("half-circle", "full-circle", "circle", "quarter-circle", "three-quarter-circle")
        # long one-piece dresses are drafted as bodice + lower piece (sewn at the waist, merged after the simulation)
        # so the bodice can be arranged close to the shoulders; short one-piece tops stay a single piece
        split_waist = one_piece and bottom_h < body.h_waist - 150
        if split_waist:
            bottom_h_bodice = body.h_waist
            bt = "waist"
        else:
            bottom_h_bodice = bottom_h
            bt = "hem" if one_piece else "waist"
        front = bodice_piece(body, s, "front", bottom_h_bodice, hem_hw, strapless=strapless, straps=straps, bottom_token=bt, split_bottom=circle)
        back = bodice_piece(body, s, "back", bottom_h_bodice, hem_hw, strapless=strapless, straps=straps, bottom_token=bt, split_bottom=circle)
        plan.pieces.extend([front, back])
        if split_waist:
            lower = lower_body_pieces(body, front.edge_length("hem") / 2, back.edge_length("hem") / 2, hip_hw,
                                      hem_hw if hem_hw is not None else hip_hw, body.h_waist, hem_h)
            plan.pieces.extend(lower)
            plan.seams.append(Seam("Lower_Front", "side_L", "Lower_Back", "side_L"))
            plan.seams.append(Seam("Lower_Front", "side_R", "Lower_Back", "side_R"))
            plan.seams.append(Seam("Front", "hem", "Lower_Front", "waist"))
            plan.seams.append(Seam("Back", "hem", "Lower_Back", "waist"))
            plan.merge_pairs = [["Front", "Lower_Front"], ["Back", "Lower_Back"]]
            plan.notes.append("one-piece dress built as bodice + lower piece for a stable drape; merged into single pieces after simulation")
        plan.seams.append(Seam("Front", "side_L", "Back", "side_L"))
        plan.seams.append(Seam("Front", "side_R", "Back", "side_R"))
        if not strapless:
            plan.seams.append(Seam("Front", "shoulder_L", "Back", "shoulder_L"))
            plan.seams.append(Seam("Front", "shoulder_R", "Back", "shoulder_R"))
        if strapless:
            for p in (front, back):
                p.elastic["top"] = p.edge_length("top") * 0.96
            plan.notes.append("strapless: top edges use elastic so the bodice stays up")
        if straps:
            plan.notes.append("straps are drafted as part of the front/back pieces and joined at the shoulder")
        if has_sleeves:
            armhole_len = front.edge_length("armhole_L") + back.edge_length("armhole_L")
            underarm_h = getattr(front, "meta_underarm_h", body.h_apex + 25.0)
            for side in ("L", "R"):
                sl = sleeve_piece(body, s, side, armhole_len, underarm_h, body.h_shoulder + 20.0)
                plan.pieces.append(sl)
                plan.seams.append(Seam(f"Sleeve_{side}", "underarm_back", f"Sleeve_{side}", "underarm_front", flip=True))
                plan.seams.append(Seam(f"Sleeve_{side}", "cap_front", "Front", f"armhole_{side}", gather=s.get("sleeve_style") in ("puff", "balloon")))
                plan.seams.append(Seam(f"Sleeve_{side}", "cap_back", "Back", f"armhole_{side}", gather=s.get("sleeve_style") in ("puff", "balloon")))
        if not one_piece:
            bodice_waist_len = (front.edge_length("hem_L_half") + front.edge_length("hem_R_half")) if circle else front.edge_length("hem")
            skirts, sk_seams = skirt_pieces(body, s, waist_h, hem_h, bodice_waist_len)
            plan.pieces.extend(skirts)
            plan.seams.extend(sk_seams)
            kind = s.get("skirt", "a-line")
            gather = kind in ("gathered", "dirndl", "full", "pleated", "tiered")
            if circle:
                # each quarter panel sews to the matching half of the bodice bottom edge (split at CF / CB)
                plan.seams.append(Seam("Skirt_Front_L", "waist", "Front", "hem_L_half"))
                plan.seams.append(Seam("Skirt_Front_R", "waist", "Front", "hem_R_half"))
                plan.seams.append(Seam("Skirt_Back_L", "waist", "Back", "hem_L_half"))
                plan.seams.append(Seam("Skirt_Back_R", "waist", "Back", "hem_R_half"))
            elif kind == "tiered":
                plan.seams.append(Seam("Front", "hem", "Tier1_Front", "waist", gather=gather))
                plan.seams.append(Seam("Back", "hem", "Tier1_Back", "waist", gather=gather))
            else:
                plan.seams.append(Seam("Front", "hem", "Skirt_Front", "waist", gather=gather))
                plan.seams.append(Seam("Back", "hem", "Skirt_Back", "waist", gather=gather))

    # arrangement
    for p in plan.pieces:
        if not p.arrangement:
            if p.role in ("bodice_front", "skirt_front"):
                p.arrangement = "Body_Front_Center_3" if p.role == "bodice_front" else "Leg_Skirt_Front"
            elif p.role in ("bodice_back", "skirt_back"):
                p.arrangement = "Body_Back_Center_3" if p.role == "bodice_back" else "Leg_Skirt_Back"
    # fabric
    fab_stem, matched = fabric_file_for(s.get("fabric"))
    plan.fabric = {"library_stem": fab_stem, "matched": matched, "color": parse_color(s.get("color")), "color_text": s.get("color")}
    # simulation defaults
    long_dress = hem_h < body.h_knee - 100
    tiered = any("Tier" in p.name for p in plan.pieces)
    plan.simulation = {"steps": int(s.get("simulate_steps", 260 if tiered else 160 if long_dress else 120)),
                       "particle_distance": float(s.get("particle_distance", 20.0))}
    plan.resolve_seams()
    return plan


if __name__ == "__main__":
    import json
    import sys
    spec = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"silhouette": "fit-and-flare", "neckline": "v", "sleeve": "short", "length": "knee"}
    plan = plan_garment(spec, Body())
    d = plan.to_dict()
    for p in d["pieces"]:
        print(p["name"], p["role"], "arr=", p["arrangement"], "centre=", p["centre_height"], "h=", p["height"],
              [(e["name"], e["length"]) for e in p["edges"]])
    for sm in d["seams"]:
        print("seam", sm)
    print("warnings", d["warnings"])
    print("notes", d["notes"])
    print("fabric", d["fabric"])
