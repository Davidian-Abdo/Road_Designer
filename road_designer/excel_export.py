"""Excel / CSV export of the profil-en-long table with cubature columns.

The exported file is what the BET reviewer opens in Excel-FR alongside the DXF.
Columns are deliberately French.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Union

import io
import pandas as pd

if TYPE_CHECKING:
    from .road_design import RoadDesign


# ─────────────────────────────────────────────────────────────────────────────

COLUMNS = [
    "Profil",
    "PK (m)",
    "Distance Partielle (m)",
    "Cote TN (m)",
    "Cote Projet (m)",
    "h = Projet - TN (m)",        # >0 remblai, <0 déblai
    "Pente entrante (%)",
    "V Déblai segment (m³)",
    "V Remblai segment (m³)",
    "V Déblai cumulé (m³)",
    "V Remblai cumulé (m³)",
    "Bruckner M(PK) (m³)",
]


def to_dataframe(design: "RoadDesign") -> pd.DataFrame:
    """Build the Excel-ready dataframe from a design.

    Per-segment volumes are reported on the row of the segment **end**,
    consistent with the way Distance Partielle is shown.
    """
    cub = design.cubatures
    if cub is None:
        raise RuntimeError(
            "design.cubatures is None. Call compute_cubatures(design) first."
        )

    n = len(design.vert_pks)
    rows = []

    # Per-PVI grade lookup — we report the incoming grade at each station
    incoming_grade = [None] * n
    for i in range(1, n):
        dpk = design.vert_pks[i] - design.vert_pks[i - 1]
        if dpk > 0:
            incoming_grade[i] = 100.0 * (
                design.v_align.get_z(design.vert_pks[i])
                - design.v_align.get_z(design.vert_pks[i - 1])
            ) / dpk

    for i in range(n):
        rows.append({
            COLUMNS[0]:  f"P{i + 1}",
            COLUMNS[1]:  round(float(design.vert_pks[i]), 3),
            COLUMNS[2]:  ("" if i == 0
                          else round(float(design.seg_lengths[i]), 3)),
            COLUMNS[3]:  round(float(design.vert_ground_z[i]), 3),
            COLUMNS[4]:  round(float(design.vert_proj_z[i]), 3),
            COLUMNS[5]:  round(float(cub.h_per_vertex[i]), 3),
            COLUMNS[6]:  ("" if incoming_grade[i] is None
                          else round(incoming_grade[i], 3)),
            COLUMNS[7]:  ("" if i == 0
                          else round(float(cub.V_deb_per_seg[i - 1]), 2)),
            COLUMNS[8]:  ("" if i == 0
                          else round(float(cub.V_rem_per_seg[i - 1]), 2)),
            COLUMNS[9]:  round(float(cub.V_deb_cum[i]), 2),
            COLUMNS[10]: round(float(cub.V_rem_cum[i]), 2),
            COLUMNS[11]: round(float(cub.bruckner[i]), 2),
        })
    df = pd.DataFrame(rows, columns=COLUMNS)
    return df


def write_xlsx(design: "RoadDesign", out_path: Union[str, Path]) -> Path:
    """Write the tableau as an .xlsx with frozen header + totals footer."""
    out_path = Path(out_path)
    df = to_dataframe(design)
    cub = design.cubatures

    with pd.ExcelWriter(out_path, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Profil en long", index=False,
                    startrow=0, freeze_panes=(1, 0))
        ws = xl.sheets["Profil en long"]

        # Auto-fit columns approximately
        for j, col in enumerate(df.columns, start=1):
            max_len = max(len(str(col)),
                          *(len(str(v)) for v in df[col].astype(str)))
            ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = (
                min(max_len + 2, 28)
            )

        # Totals footer
        total_row = len(df) + 3
        ws.cell(row=total_row, column=1, value="TOTAUX")
        ws.cell(row=total_row, column=8,
                value=round(cub.total_deb, 2))  # V Déblai segment
        ws.cell(row=total_row, column=9,
                value=round(cub.total_rem, 2))  # V Remblai segment
        ws.cell(row=total_row + 1, column=1, value="Bilan (Remb − Déb)")
        ws.cell(row=total_row + 1, column=9,
                value=round(cub.balance, 2))
        ws.cell(row=total_row + 2, column=1,
                value=f"Mode : plateforme W = {design.cfg.road_width:.2f} m, "
                f"talus déb={design.cfg.typical_section.talus_deblai_h_v:.3f}, "
                f"rem={design.cfg.typical_section.talus_remblai_h_v:.3f}")

        # REFT warnings (C6) — sheet 2
        if design.tangent_warnings:
            ws2 = xl.book.create_sheet("Avertissements REFT")
            ws2.cell(row=1, column=1, value="Avertissements REFT")
            for k, msg in enumerate(design.tangent_warnings, start=2):
                ws2.cell(row=k, column=1, value=msg)
            ws2.column_dimensions["A"].width = 80

    print(f"XLSX generated: {out_path}")
    return out_path


def write_csv(design: "RoadDesign", out_path: Union[str, Path]) -> Path:
    """Write the tableau as a UTF-8-BOM CSV (so Excel-FR auto-detects)."""
    out_path = Path(out_path)
    df = to_dataframe(design)
    df.to_csv(out_path, index=False, encoding="utf-8-sig", sep=";")
    print(f"CSV generated: {out_path}")
    return out_path


def to_xlsx_bytes(design: "RoadDesign") -> bytes:
    """In-memory XLSX (for Streamlit download_button)."""
    buf = io.BytesIO()
    df = to_dataframe(design)
    cub = design.cubatures
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Profil en long", index=False,
                    freeze_panes=(1, 0))
        ws = xl.sheets["Profil en long"]
        total_row = len(df) + 3
        ws.cell(row=total_row, column=1, value="TOTAUX")
        ws.cell(row=total_row, column=8, value=round(cub.total_deb, 2))
        ws.cell(row=total_row, column=9, value=round(cub.total_rem, 2))
    return buf.getvalue()
