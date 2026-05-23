"""CLI entry point for Road Designer V 1.0.

For the Streamlit UI see app.py (added in Step 9). For now this script
generates a DXF + XLSX from terrain_database.csv + axe.txt with the default
REFT_CAT_1 config.

Usage
-----
    python main.py [--axe AXE.txt] [--terrain TERRAIN.csv] [--out OUTDIR]
                   [--category CAT_1|CAT_2|CAT_3]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from road_designer.config import get_preset
from road_designer.road_design import build_design
from road_designer.samples_api import sample_axe_path, sample_terrain_path


def main():
    parser = argparse.ArgumentParser(description="Road Designer V 1.0 — CLI")
    parser.add_argument("--axe", default=None,
                        help="Path to the axe file "
                             "(default: samples/sample_axe.txt)")
    parser.add_argument("--terrain", default=None,
                        help="Path to the terrain CSV X,Y,Z "
                             "(default: samples/sample_terrain.csv)")
    parser.add_argument("--out", default="output",
                        help="Output directory")
    parser.add_argument("--category", default="CAT_1",
                        choices=("CAT_1", "CAT_2", "CAT_3"),
                        help="REFT road category preset")
    args = parser.parse_args()

    args.axe = args.axe or str(sample_axe_path())
    args.terrain = args.terrain or str(sample_terrain_path())

    cfg = get_preset(args.category)
    result = build_design(
        cfg,
        axe_path=Path(args.axe),
        terrain_path=Path(args.terrain),
        out_dir=Path(args.out),
    )
    print()
    print("=" * 60)
    print("Road Designer V 1.0 — build complete")
    print("=" * 60)
    print(f"  DXF      : {result['dxf']}")
    print(f"  XLSX     : {result['xlsx']}")
    print(f"  PDF plan : {result['pdf_plan']}")
    print(f"  PDF PT   : {result['pdf_pt']}")
    if result["warnings"]:
        print(f"  REFT warnings: {len(result['warnings'])} (see XLSX sheet 2)")


if __name__ == "__main__":
    main()
