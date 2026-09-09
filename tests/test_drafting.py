"""Offline tests for the drafting engine (no CLO needed): python -m pytest tests/ or run directly."""
import sys, os
from clo3d_mcp import drafting

SPECS = [
    {"silhouette": "fit-and-flare", "neckline": "v", "sleeve": "short", "length": "knee"},
    {"silhouette": "sheath", "neckline": "round", "length": "midi"},
    {"silhouette": "slip", "length": "maxi"},
    {"silhouette": "skater", "neckline": "sweetheart", "strapless": True, "length": "mini"},
    {"silhouette": "empire", "neckline": "scoop", "sleeve": "long", "sleeve_style": "puff", "length": "maxi"},
    {"garment": "skirt", "silhouette": "tiered", "length": "midi"},
    {"garment": "skirt", "silhouette": "full-circle", "length": "knee"},
    {"garment": "top", "neckline": "boat", "sleeve": "long", "length": "hip", "fit": "fitted"},
    {"silhouette": "mermaid", "neckline": "sweetheart", "strapless": True, "length": "floor"},
]


def test_plans_have_no_length_warnings():
    body = drafting.Body()
    for spec in SPECS:
        plan = drafting.plan_garment(spec, body)
        d = plan.to_dict()
        assert d["pieces"], spec
        for p in d["pieces"]:
            # every edge starts with a corner point so CLO line indices match edge order
            pts = p["points"]
            assert pts[0][2] == 0
        bad = [w for w in d["warnings"] if "differs" in w or "do not match" in w]
        assert not bad, (spec, bad)


if __name__ == "__main__":
    test_plans_have_no_length_warnings()
    print("ok")
