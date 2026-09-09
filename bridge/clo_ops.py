"""High-level CLO operations that run INSIDE CLO (imported by clo_bridge.py; hot-reload with `reload_ops`).

register(ns, log) -> {command_name: handler(params) -> jsonable}
ns holds the CLO api modules: import_api, export_api, fabric_api, pattern_api, utility_api, rest_api, ApiTypes
All lengths are millimetres; heights are world Y above the floor.
"""
import json
import os
import time

VIEW_INDEX = {"bottom": 0, "3/4-right": 1, "three-quarter": 1, "front": 2, "3/4-left": 3, "right": 4, "top": 5,
              "left": 6, "focus": 7, "back": 8, "fit": 9}


def register(ns, log):
    pattern_api = ns["pattern_api"]
    utility_api = ns["utility_api"]
    export_api = ns["export_api"]
    import_api = ns["import_api"]
    fabric_api = ns["fabric_api"]
    ApiTypes = ns["ApiTypes"]

    # ------------------------------------------------------------------ helpers
    def _json_or_raw(s):
        if isinstance(s, str):
            try:
                return json.loads(s)
            except Exception:
                return s
        return s

    def _arrangement_map():
        return {a["ArrangementName"]: int(a["ArrangementIndex"]) for a in pattern_api.GetArrangementList()}

    def _pattern_index(ref):
        """Accept an int index or a pattern name."""
        if isinstance(ref, int):
            return ref
        if isinstance(ref, str) and ref.lstrip("-").isdigit():
            return int(ref)
        n = pattern_api.GetPatternCount()
        for i in range(n):
            if pattern_api.GetPatternPieceName(i) == ref:
                return i
        raise ValueError("no pattern named %r (have %s)" % (ref, [pattern_api.GetPatternPieceName(i) for i in range(n)]))

    def _pattern_names():
        return [pattern_api.GetPatternPieceName(i) for i in range(pattern_api.GetPatternCount())]

    def _garment_bbox():
        """3D bounding box of the current garment via a quick OBJ export (mm)."""
        o = ApiTypes.ImportExportOption()
        o.bExportGarment = True
        o.bExportAvatar = False
        o.bSingleObject = True
        o.scale = 1.0
        o.bThin = True
        path = os.path.join(utility_api.GetCLOTemporaryFolderPath(), "clo3d_mcp_bbox.obj")
        export_api.ExportOBJ(path, o)
        xs = []
        ys = []
        zs = []
        with open(path) as f:
            for line in f:
                if line.startswith("v "):
                    _, x, y, z = line.split()[:4]
                    xs.append(float(x))
                    ys.append(float(y))
                    zs.append(float(z))
        if not ys:
            return None
        return {"min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)],
                "centre": [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2]}

    # ------------------------------------------------------------------ scene
    def scene_info(params):
        n = pattern_api.GetPatternCount()
        return {
            "project": utility_api.GetProjectName(),
            "project_path": utility_api.GetProjectFilePath(),
            "clo_version": "%d.%d.%d" % (utility_api.GetMajorVersion(), utility_api.GetMinorVersion(), utility_api.GetPatchVersion()),
            "pattern_count": n,
            "patterns": [{"index": i, "name": pattern_api.GetPatternPieceName(i),
                          "arrangement": (pattern_api.GetArrangementOfPattern(i) or {}).get("ArrangementName", ""),
                          "fabric_index": pattern_api.GetPatternPieceFabricIndex(i)} for i in range(n)],
            "avatars": list(export_api.GetAvatarNameList() or []),
            "fabric_count": fabric_api.GetFabricCount(True),
            "fabrics": [{"index": i, "name": fabric_api.GetFabricName(i)} for i in range(fabric_api.GetFabricCount(True))],
            "colorways": list(export_api.GetColorwayNameList() or []),
            "current_colorway": utility_api.GetCurrentColorwayIndex(),
            "seam_groups": pattern_api.GetSeamlinePairGroupCount(),
            "temp_folder": utility_api.GetCLOTemporaryFolderPath(),
            "asset_folder": utility_api.GetCLOAssetFolderPath(True),
        }

    def clear_garment(params):
        """Delete every pattern piece (keeps avatar, fabrics stay in the object browser)."""
        n = pattern_api.GetPatternCount()
        for _ in range(n):
            pattern_api.DeletePatternPiece(0)
        return {"deleted": n, "pattern_count": pattern_api.GetPatternCount()}

    def new_project(params):
        utility_api.NewProject()
        return {"pattern_count": pattern_api.GetPatternCount(), "avatars": list(export_api.GetAvatarNameList() or [])}

    def open_file(params):
        path = params["path"]
        mode = params.get("mode", "replace")
        ext = os.path.splitext(path)[1].lower()
        if ext == ".zprj":
            opt = ApiTypes.ImportZPRJOption()
            opt.bAppend = (mode == "append")
            opt.bLoadGarment = params.get("load_garment", True)
            opt.bLoadAvatar = params.get("load_avatar", True)
            ok = import_api.ImportZprj(path, opt)
        elif ext == ".zpac":
            opt = ApiTypes.ImportExportOption()
            opt.bAdd = (mode == "append")
            ok = import_api.ImportZpac(path, opt)
        elif ext == ".avt":
            ok = import_api.ImportAvatar(path, ApiTypes.ImportExportOption())
        elif ext == ".dxf":
            opt = ApiTypes.ImportDxfOption()
            opt.m_bAppend = (mode == "append")
            opt.m_bAutoScale = True
            opt.m_bAutoDistribute = True
            ok = import_api.ImportDXF(path, opt)
        elif ext == ".json":
            ok = pattern_api.ImportPatternJSON(path)
        else:
            ok = import_api.ImportFile(path)
        return {"ok": bool(ok), "path": path, "pattern_count": pattern_api.GetPatternCount(),
                "avatars": list(export_api.GetAvatarNameList() or [])}

    def save_project(params):
        path = params["path"]
        ext = os.path.splitext(path)[1].lower()
        if ext == ".zpac":
            out = export_api.ExportZPac(path)
        else:
            out = export_api.ExportZPrj(path, bool(params.get("thumbnail", False)))
        if not out:
            raise RuntimeError("export returned an empty path (failed)")
        return {"path": out}

    def export_file(params):
        path = params["path"]
        ext = os.path.splitext(path)[1].lower()
        o = ApiTypes.ImportExportOption()
        o.bExportGarment = params.get("garment", True)
        o.bExportAvatar = params.get("avatar", False)
        o.bSingleObject = params.get("single_object", True)
        o.scale = float(params.get("scale", 1.0))
        o.bSaveColorWays = params.get("colorways", False)
        if ext == ".obj":
            out = export_api.ExportOBJ(path, o)
        elif ext == ".fbx":
            out = export_api.ExportFBX(path, o)
        elif ext == ".glb":
            out = export_api.ExportGLB(path, o)
        elif ext == ".gltf":
            out = export_api.ExportGLTF(path, o, False)
        elif ext == ".dxf":
            d = ApiTypes.ExportDxfOption()
            d.m_bMetric = True
            out = export_api.ExportDXF(path, d)
        elif ext == ".json":
            out = pattern_api.ExportPatternJSON(path)
        elif ext in (".zprj", ".zpac"):
            return save_project(params)
        else:
            raise ValueError("unsupported export extension %r" % ext)
        return {"result": out, "path": path}

    # ------------------------------------------------------------------ views / snapshots
    def snapshot(params):
        """Screenshot(s) of the 3D window. views: list of names (front, back, left, right, 3/4-right, 3/4-left, top)."""
        views = params.get("views") or ["front"]
        folder = params.get("folder") or utility_api.GetCLOTemporaryFolderPath()
        prefix = params.get("prefix", "clo3d_mcp_snap")
        zoom = params.get("zoom", True)
        out = []
        for v in views:
            idx = VIEW_INDEX.get(str(v).lower(), None)
            if idx is None and isinstance(v, int):
                idx = v
            if idx is None:
                raise ValueError("unknown view %r (use %s)" % (v, sorted(VIEW_INDEX)))
            utility_api.SetCamViewPoint(idx)
            if zoom:
                utility_api.SetZoomView()
            path = os.path.join(folder, "%s_%s_%d.png" % (prefix, str(v).replace("/", ""), int(time.time() * 1000) % 100000000))
            p = export_api.ExportThumbnail3D(path)
            out.append({"view": v, "path": p})
        return {"images": out}

    def snapshot_2d(params):
        folder = params.get("folder") or utility_api.GetCLOTemporaryFolderPath()
        path = os.path.join(folder, "clo3d_mcp_2d_%d.png" % (int(time.time() * 1000) % 100000000))
        res = export_api.ExportSnapshot2D(path, int(params.get("mode", 0)))
        return {"result": res, "path": path}

    def set_view(params):
        idx = VIEW_INDEX.get(str(params.get("view", "front")).lower(), 2)
        utility_api.SetCamViewPoint(idx)
        if params.get("zoom", True):
            utility_api.SetZoomView()
        return {"view": idx}

    # ------------------------------------------------------------------ avatar
    def avatar_info(params):
        names = list(export_api.GetAvatarNameList() or [])
        out = {"avatars": names, "measurements": {}}
        if names:
            idx = int(params.get("index", 0))
            meas = {}
            for m in utility_api.GetAvatarMeasurements(idx):
                meas.setdefault(m.measurementName, {"type": m.measurementType, "value": m.value, "unit": m.unit})
            out["measurements"] = meas
            out["measurement_count"] = len(meas)
        return out

    def load_avatar(params):
        path = params["path"]
        if params.get("replace", True):
            n = export_api.GetAvatarCount()
            if n:
                utility_api.DeleteAvatar(list(range(n)))
        ok = import_api.ImportAvatar(path, ApiTypes.ImportExportOption())
        return {"ok": bool(ok), "avatars": list(export_api.GetAvatarNameList() or [])}

    def arrangement_points(params):
        return {"points": pattern_api.GetArrangementList()}

    def calibrate_arrangement(params):
        """Measure the world centre of a 100 mm test square placed at each arrangement point (SetArrangement only)."""
        names = params.get("names") or list(_arrangement_map().keys())
        arr = _arrangement_map()
        out = {}
        for name in names:
            if name not in arr:
                out[name] = None
                continue
            sq = pattern_api.CreatePatternWithPoints([(5000.0, 0.0, 0), (5100.0, 0.0, 0), (5100.0, 100.0, 0), (5000.0, 100.0, 0)])
            pattern_api.SetArrangement(sq, arr[name])
            bb = _garment_bbox()
            pattern_api.DeletePatternPiece(sq)
            out[name] = bb["centre"] if bb else None
        return {"points": out}

    # ------------------------------------------------------------------ patterns
    def pattern_list(params):
        n = pattern_api.GetPatternCount()
        detail = params.get("detail", False)
        out = []
        for i in range(n):
            item = {"index": i, "name": pattern_api.GetPatternPieceName(i),
                    "arrangement": (pattern_api.GetArrangementOfPattern(i) or {}).get("ArrangementName", ""),
                    "fabric_index": pattern_api.GetPatternPieceFabricIndex(i),
                    "bbox": pattern_api.GetBoundingBoxOfPattern(i), "pos_2d": pattern_api.GetPatternPiecePos(i)}
            if detail:
                li = _json_or_raw(pattern_api.GetPatternLineInfo(i))
                if isinstance(li, dict):
                    item["lines"] = [{"line": l["lineIndex"], "length": round(l["length"], 1), "location": l.get("location"),
                                      "start": l.get("start"), "end": l.get("end")} for l in li.get("lines", [])]
                item["seam_groups"] = list(pattern_api.GetSeamlinePairGroupListInPattern(i))
            out.append(item)
        return {"patterns": out, "count": n, "seam_groups": pattern_api.GetSeamlinePairGroupCount()}

    def pattern_info(params):
        i = _pattern_index(params["pattern"])
        return {
            "index": i,
            "name": pattern_api.GetPatternPieceName(i),
            "bbox": pattern_api.GetBoundingBoxOfPattern(i),
            "pos_2d": pattern_api.GetPatternPiecePos(i),
            "line_info": _json_or_raw(pattern_api.GetPatternLineInfo(i)),
            "input_info": _json_or_raw(pattern_api.GetPatternInputInformation(i)),
            "fabric_index": pattern_api.GetPatternPieceFabricIndex(i),
            "arrangement": pattern_api.GetArrangementOfPattern(i),
            "seam_groups": list(pattern_api.GetSeamlinePairGroupListInPattern(i)),
            "layer": pattern_api.GetPatternLayer(i),
            "particle_distance": pattern_api.GetParticleDistanceOfPattern(i),
        }

    def create_pattern(params):
        pts = [(float(p[0]), float(p[1]), int(p[2]) if len(p) > 2 else 0) for p in params["points"]]
        if len(pts) < 3:
            raise ValueError("need at least 3 points")
        idx = pattern_api.CreatePatternWithPoints(pts)
        if params.get("name"):
            pattern_api.SetPatternPieceName(idx, params["name"])
        if params.get("arrangement"):
            arr = _arrangement_map()
            if params["arrangement"] not in arr:
                raise ValueError("unknown arrangement point %r" % params["arrangement"])
            pattern_api.SetArrangement(idx, arr[params["arrangement"]])
        return {"index": idx, "name": pattern_api.GetPatternPieceName(idx)}

    def delete_patterns(params):
        refs = params.get("patterns") or []
        idxs = sorted({_pattern_index(r) for r in refs}, reverse=True)
        for i in idxs:
            pattern_api.DeletePatternPiece(i)
        return {"deleted": len(idxs), "pattern_count": pattern_api.GetPatternCount()}

    def set_arrangement(params):
        i = _pattern_index(params["pattern"])
        arr = _arrangement_map()
        name = params["point"]
        if name not in arr:
            raise ValueError("unknown arrangement point %r" % name)
        pattern_api.SetArrangement(i, arr[name])
        return {"index": i, "arrangement": pattern_api.GetArrangementOfPattern(i)}

    def move_points(params):
        """moves: [{point: int, x: float, y: float}] in 2D pattern space; or offsets with dx/dy."""
        i = _pattern_index(params["pattern"])
        info = _json_or_raw(pattern_api.GetPatternInputInformation(i))
        pts = {}
        try:
            for entry in info["Pattern InputInformation"][0]["PointList"]:
                if "Point index" in entry:
                    pts[int(entry["Point index"])] = (entry["Point positionX"], entry["Point positionY"])
        except Exception:
            pass
        done = []
        for mv in params["moves"]:
            pi = int(mv["point"])
            if "x" in mv and "y" in mv:
                x, y = float(mv["x"]), float(mv["y"])
            else:
                ox, oy = pts.get(pi, (0.0, 0.0))
                x, y = ox + float(mv.get("dx", 0.0)), oy + float(mv.get("dy", 0.0))
            pattern_api.MovePatternPoint(i, pi, x, y)
            done.append({"point": pi, "x": x, "y": y})
        return {"index": i, "moved": done}

    def pattern_ops(params):
        """Misc per-pattern operations: rename, move_2d, flip, copy, symmetry, unfold, layer, particle_distance, freeze, hide."""
        i = _pattern_index(params["pattern"])
        op = params["op"]
        a = params.get("args", {})
        if op == "rename":
            pattern_api.SetPatternPieceName(i, a["name"])
        elif op == "move_2d":
            if "x" in a:
                pattern_api.SetPatternPiecePos(i, float(a["x"]), float(a["y"]))
            else:
                pattern_api.SetPatternPieceMove(i, float(a.get("dx", 0)), float(a.get("dy", 0)))
        elif op == "flip":
            pattern_api.FlipPatternPiece(i, bool(a.get("horizontal", True)), bool(a.get("each", True)))
        elif op == "copy":
            return {"new_index": pattern_api.CopyPatternPieceMove(i, float(a.get("dx", 300)), float(a.get("dy", 0)))}
        elif op == "symmetry":
            pattern_api.SymmetryPatternPiece(i, bool(a.get("with_sewing", True)))
        elif op == "unfold":
            return {"ok": pattern_api.UnfoldPatternPiece(i, int(a["line"]), bool(a.get("half_symmetry", True)))}
        elif op == "layer":
            pattern_api.SetPatternLayer(i, int(a["layer"]))
        elif op == "particle_distance":
            pattern_api.SetParticleDistanceOfPattern(i, float(a["mm"]))
        elif op == "freeze":
            pattern_api.SetPatternFreeze(i, bool(a.get("on", True)))
        elif op == "hide":
            pattern_api.SetPatternHide3D(i, bool(a.get("on", True)))
        elif op == "strengthen":
            pattern_api.SetPatternStrengthen(i, bool(a.get("on", True)))
        elif op == "elastic":
            line = int(a.get("line", -1))
            pattern_api.SetPatternPieceElastic(i, line, bool(a.get("on", True)))
            if a.get("total_length"):
                pattern_api.SetPatternPieceElasticTotalLength(i, line, float(a["total_length"]))
            if a.get("strength"):
                pattern_api.SetPatternPieceElasticStrength(i, line, float(a["strength"]))
        elif op == "shirring":
            line = int(a.get("line", -1))
            pattern_api.SetPatternPieceShirring(i, line, bool(a.get("on", True)))
        elif op == "delete_line":
            pattern_api.DeleteLine(i, int(a["line"]))
        elif op == "delete_point":
            pattern_api.DeletePoint(i, int(a["point"]))
        else:
            raise ValueError("unknown op %r" % op)
        return {"index": i, "op": op, "ok": True}

    # ------------------------------------------------------------------ sewing
    def sew(params):
        ia = _pattern_index(params["pattern_a"])
        ib = _pattern_index(params["pattern_b"])
        ok = pattern_api.AddSeamlinePairGroup(ia, int(params["line_a"]), ib, int(params["line_b"]),
                                              bool(params.get("dir_a", True)), bool(params.get("dir_b", True)))
        return {"ok": bool(ok), "seam_groups": pattern_api.GetSeamlinePairGroupCount()}

    def seams(params):
        n = pattern_api.GetSeamlinePairGroupCount()
        members = {}
        for p in range(pattern_api.GetPatternCount()):
            for g in pattern_api.GetSeamlinePairGroupListInPattern(p):
                members.setdefault(int(g), []).append(pattern_api.GetPatternPieceName(p))
        return {"count": n, "groups": [{"index": g, "name": pattern_api.GetSeamlinePairGroupName(g), "patterns": members.get(g, [])} for g in range(n)]}

    def deactivate_sewing(params):
        return {"changed": pattern_api.ActivateAllPatterns(bool(params.get("activate", True)), bool(params.get("include_sewing", True)))}

    # ------------------------------------------------------------------ fabrics
    def fabric_list(params):
        n = fabric_api.GetFabricCount(True)
        out = []
        for i in range(n):
            try:
                info = fabric_api.GetFabricInformation(i)
            except Exception:
                info = {}
            out.append({"index": i, "name": fabric_api.GetFabricName(i), "info": info})
        return {"fabrics": out, "current": fabric_api.GetCurrentFabricIndex()}

    def add_fabric(params):
        path = params["path"]
        idx = fabric_api.AddFabric(path)
        if params.get("name"):
            fabric_api.SetFabricName(idx, params["name"])
        return {"index": idx, "name": fabric_api.GetFabricName(idx)}

    def assign_fabric(params):
        fi = int(params["fabric_index"])
        refs = params.get("patterns")
        idxs = [_pattern_index(r) for r in refs] if refs else list(range(pattern_api.GetPatternCount()))
        opt = int(params.get("option", 3))
        res = [bool(fabric_api.AssignFabricToPattern(fi, i, opt)) for i in idxs]
        return {"assigned": res, "patterns": idxs}

    def _apply_color(fi, rgb, keep_texture=False, faces=(0, 1, 2)):
        """Set a flat base colour. Library fabrics often carry a coloured base texture that tints the colour,
        so the base texture map is removed unless keep_texture is set (normal/roughness maps stay)."""
        r, g, b = rgb
        res = []
        for face in faces:
            res.append(bool(fabric_api.SetFabricPBRMaterialBaseColor(fi, int(face), r, g, b, 1.0)))
        if not keep_texture:
            _neutralise_texture(fi)
        _make_opaque(fi)
        return res

    SHEER_HINTS = ("chiffon", "organza", "tulle", "mesh", "lace", "voile", "georgette", "gauze", "eyelet", "crochet", "pointelle", "net")

    def _make_opaque(fi):
        """Some library fabrics (e.g. Crepe CDC) ship with an alpha/opacity map that renders see-through patches
        on dark colours; clear it unless the fabric is meant to be sheer."""
        try:
            name = (fabric_api.GetFabricName(fi) or "").lower()
            if any(h in name for h in SHEER_HINTS):
                return "sheer-kept"
            fabric_api.SetCurrentFabricIndex(fi)
            fabric_api.SetOpacityMapImageGivenFilePath("")
            return "cleared"
        except Exception:
            return "failed"

    def _neutralise_texture(fi):
        """Library fabrics carry coloured base textures (e.g. pink satin) that tint any flat colour.
        Desaturate the texture (keeps the weave detail). SetBaseTextureMapImageDesaturation wants the
        colorway-space fabric index, so find it by matching the colour we just set; fall back to clearing the map."""
        try:
            cw = utility_api.GetCurrentColorwayIndex()
            target = fabric_api.GetFabricPBRMaterialBaseColor(fi, 0)
            n_cw = fabric_api.GetFabricCount(True)
            hit = None
            for i in range(n_cw):
                col = fabric_api.GetFabricPBRMaterialBaseColor(cw, i, 0)
                if col and all(abs(float(col[k]) - float(target[k])) < 1e-3 for k in range(3)):
                    hit = i
            if hit is not None:
                utility_api.SetBaseTextureMapImageDesaturation(hit, cw, True)
                return "desaturated"
        except Exception:
            pass
        try:
            fabric_api.SetCurrentFabricIndex(fi)
            fabric_api.SetBaseTextureMapImageGivenFilePath("")
            return "cleared"
        except Exception:
            return "failed"

    def set_fabric_color(params):
        fi = int(params["fabric_index"])
        rgb = [float(v) for v in params["rgb"][:3]]
        faces = params.get("faces", [0, 1, 2])
        res = _apply_color(fi, rgb, keep_texture=bool(params.get("keep_texture", False)), faces=faces)
        utility_api.UpdateColorways(True)
        return {"ok": res}

    def set_fabric_texture(params):
        fi = int(params["fabric_index"])
        path = params["path"]
        kind = params.get("map", "base")
        face = int(params.get("face", 0))
        # these setters act on the *current* fabric (single-argument API)
        fabric_api.SetCurrentFabricIndex(fi)
        if kind == "base":
            fabric_api.SetBaseTextureMapImageGivenFilePath(path)
        elif kind == "normal":
            fabric_api.SetNormalMapImageGivenFilePath(path)
        elif kind == "roughness":
            fabric_api.SetRoughnessMapImageGivenFilePath(path)
        elif kind == "opacity":
            fabric_api.SetOpacityMapImageGivenFilePath(path)
        elif kind == "displacement":
            fabric_api.SetDisplacementMapImageGivenFilePath(path)
        elif kind == "metalness":
            fabric_api.SetMetalnessMapImageGivenFilePath(path)
        else:
            raise ValueError("unknown map type %r" % kind)
        utility_api.UpdateColorways(True)
        return {"ok": True}

    def fabric_physics(params):
        """Overwrite the physical properties of a fabric with a JFAB-style json file (ChangeFabricWithJson)."""
        fi = int(params["fabric_index"])
        ok = fabric_api.ChangeFabricWithJson(fi, params["json_path"])
        return {"ok": bool(ok)}

    # ------------------------------------------------------------------ simulation
    def simulate(params):
        steps = int(params.get("steps", 100))
        if params.get("quality") is not None:
            utility_api.SetSimulationQuality(int(params["quality"]), int(params.get("mode", 0)))
        if params.get("particle_distance"):
            pattern_api.SetParticleDistanceOfPatterns(float(params["particle_distance"]))
        t0 = time.time()
        ok = utility_api.Simulate(steps)
        return {"ok": bool(ok), "steps": steps, "seconds": round(time.time() - t0, 2)}

    def reset_layers(params):
        """Set every pattern piece back to layer 0 (removes the layer tint after stacked pieces have settled)."""
        n = pattern_api.GetPatternCount()
        changed = 0
        for i in range(n):
            try:
                if pattern_api.GetPatternLayer(i) != 0:
                    pattern_api.SetPatternLayer(i, 0)
                    changed += 1
            except Exception:
                pass
        return {"reset": changed}

    def merge_pieces(params):
        """Merge pairs of pieces joined by a 1:1 seam into single pieces (MergeSewnPatterns). pairs: [[base, other], ...]"""
        out = []
        for base, other in params.get("pairs", []):
            try:
                ia, ib = _pattern_index(base), _pattern_index(other)
                ok = pattern_api.MergeSewnPatterns(ia, ib)
                out.append({"base": base, "other": other, "ok": bool(ok)})
            except Exception as exc:
                out.append({"base": base, "other": other, "ok": False, "error": str(exc)})
        return {"merged": out, "pattern_count": pattern_api.GetPatternCount(), "names": _pattern_names()}

    def reset_arrangement(params):
        utility_api.ResetClothArrangement()
        return {"ok": True}

    # ------------------------------------------------------------------ garment builder
    def build_garment(params):
        """Create pieces, arrange, sew, apply fabric and colour from a plan produced by clo3d_mcp.drafting."""
        plan = params["plan"]
        opts = params.get("options", {})
        t0 = time.time()
        report = {"pieces": {}, "seams": [], "warnings": list(plan.get("warnings", [])), "steps": []}
        if opts.get("replace", True) and pattern_api.GetPatternCount():
            report["steps"].append("cleared %d existing patterns" % pattern_api.GetPatternCount())
            clear_garment({})
        arr = _arrangement_map()
        names = {}
        for piece in plan["pieces"]:
            pts = [(float(p[0]), float(p[1]), int(p[2])) for p in piece["points"]]
            idx = pattern_api.CreatePatternWithPoints(pts)
            if idx is None or idx < 0:
                raise RuntimeError("CreatePatternWithPoints failed for %s" % piece["name"])
            pattern_api.SetPatternPieceName(idx, piece["name"])
            names[piece["name"]] = idx
            report["pieces"][piece["name"]] = idx
        # arrangement (direct SetArrangement places the piece centred on the point)
        for piece in plan["pieces"]:
            point = piece.get("arrangement")
            idx = names[piece["name"]]
            if point and point in arr:
                pattern_api.SetArrangement(idx, arr[point])
            elif point:
                report["warnings"].append("arrangement point %r not found for %s" % (point, piece["name"]))
        # sewing
        for s in plan["seams"]:
            ia, ib = names[s["piece_a"]], names[s["piece_b"]]
            ok = pattern_api.AddSeamlinePairGroup(ia, int(s["line_a"]), ib, int(s["line_b"]), bool(s.get("dir_a", True)), bool(s.get("dir_b", True)))
            report["seams"].append({"a": "%s:%d" % (s["piece_a"], s["line_a"]), "b": "%s:%d" % (s["piece_b"], s["line_b"]), "ok": bool(ok)})
            if not ok:
                report["warnings"].append("seam failed: %s:%d <-> %s:%d" % (s["piece_a"], s["line_a"], s["piece_b"], s["line_b"]))
        # layers (stacked pieces) + elastic edges
        if any(int(p.get("layer", 0)) for p in plan["pieces"]):
            try:
                utility_api.SetSimulationLayerBasedCollisionDetection(True)
            except Exception as exc:
                report["warnings"].append("layer collision setting failed: %s" % exc)
        for piece in plan["pieces"]:
            idx = names[piece["name"]]
            if int(piece.get("layer", 0)):
                try:
                    pattern_api.SetPatternLayer(idx, int(piece["layer"]))
                except Exception as exc:
                    report["warnings"].append("layer failed on %s: %s" % (piece["name"], exc))
            for el in piece.get("elastic", []) or []:
                try:
                    pattern_api.SetPatternPieceElastic(idx, int(el["line"]), True)
                    if el.get("total_length"):
                        pattern_api.SetPatternPieceElasticTotalLength(idx, int(el["line"]), float(el["total_length"]))
                except Exception as exc:
                    report["warnings"].append("elastic failed on %s line %s: %s" % (piece["name"], el.get("line"), exc))
        # fabric
        fab = plan.get("fabric") or {}
        if fab.get("path"):
            try:
                fi = fabric_api.AddFabric(fab["path"])
                report["fabric_index"] = fi
                for idx in names.values():
                    fabric_api.AssignFabricToPattern(fi, idx, 3)
                col = fab.get("color")
                if col:
                    _apply_color(fi, [float(v) for v in col[:3]], keep_texture=bool(fab.get("keep_texture", False)))
                utility_api.UpdateColorways(True)
            except Exception as exc:
                report["warnings"].append("fabric step failed: %s" % exc)
        if any(int(p.get("layer", 0)) for p in plan["pieces"]):
            try:
                utility_api.SetShowHideColorOptions(4, False)   # hide the green layer tint in the 3D window
            except Exception:
                pass
        sim = plan.get("simulation") or {}
        if sim.get("particle_distance"):
            pattern_api.SetParticleDistanceOfPatterns(float(sim["particle_distance"]))
        report["seconds"] = round(time.time() - t0, 2)
        report["pattern_count"] = pattern_api.GetPatternCount()
        report["seam_groups"] = pattern_api.GetSeamlinePairGroupCount()
        return report

    return {
        "scene_info": scene_info,
        "clear_garment": clear_garment,
        "new_project": new_project,
        "open_file": open_file,
        "save_project": save_project,
        "export_file": export_file,
        "snapshot": snapshot,
        "snapshot_2d": snapshot_2d,
        "set_view": set_view,
        "avatar_info": avatar_info,
        "load_avatar": load_avatar,
        "arrangement_points": arrangement_points,
        "calibrate_arrangement": calibrate_arrangement,
        "pattern_list": pattern_list,
        "pattern_info": pattern_info,
        "create_pattern": create_pattern,
        "delete_patterns": delete_patterns,
        "set_arrangement": set_arrangement,
        "move_points": move_points,
        "pattern_ops": pattern_ops,
        "sew": sew,
        "seams": seams,
        "deactivate_sewing": deactivate_sewing,
        "fabric_list": fabric_list,
        "add_fabric": add_fabric,
        "assign_fabric": assign_fabric,
        "set_fabric_color": set_fabric_color,
        "set_fabric_texture": set_fabric_texture,
        "fabric_physics": fabric_physics,
        "simulate": simulate,
        "reset_arrangement": reset_arrangement,
        "reset_layers": reset_layers,
        "merge_pieces": merge_pieces,
        "build_garment": build_garment,
    }
