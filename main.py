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


def main():
    parser = argparse.ArgumentParser(description="Road Designer V 1.0 — CLI")
    parser.add_argument("--axe", default="axe.txt",
                        help="Path to the axe file")
    parser.add_argument("--terrain", default="terrain_database.csv",
                        help="Path to the terrain CSV (X,Y,Z)")
    parser.add_argument("--out", default="output",
                        help="Output directory")
    parser.add_argument("--category", default="CAT_1",
                        choices=("CAT_1", "CAT_2", "CAT_3"),
                        help="REFT road category preset")
    args = parser.parse_args()

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
    print(f"  DXF : {result['dxf']}")
    print(f"  XLSX: {result['xlsx']}")
    if result["warnings"]:
        print(f"  REFT warnings: {len(result['warnings'])} (see XLSX sheet 2)")


if __name__ == "__main__":
    main()
