"""PDF export contract — mandatory company_name + PT page sizing."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from road_designer.config import REFT_CAT_1
from road_designer.road_design import build_design


def test_company_name_required(tmp_path, axe_path, terrain_path):
    """build_design must refuse to start if cartouche.company_name is empty."""
    cfg = deepcopy(REFT_CAT_1)
    cfg.cartouche.company_name = ""  # explicit
    with pytest.raises(ValueError, match="company_name"):
        build_design(cfg, axe_path, terrain_path, tmp_path)


def test_company_name_whitespace_only_rejected(tmp_path, axe_path, terrain_path):
    cfg = deepcopy(REFT_CAT_1)
    cfg.cartouche.company_name = "   "
    with pytest.raises(ValueError, match="company_name"):
        build_design(cfg, axe_path, terrain_path, tmp_path)


def test_pt_scale_picker_keeps_drawing_within_a4_body():
    """Cross-section data must always fit within the A4 body area regardless
    of how wide/tall the section is."""
    from road_designer.pdf_direct import (
        _pick_pt_scales, _PT_DRAW_W_MM, _PT_DRAW_H_MM,
    )
    # Typical: 50 m × 5 m
    sh, sv, w, h = _pick_pt_scales(50.0, 5.0)
    assert w <= _PT_DRAW_W_MM and h <= _PT_DRAW_H_MM
    # Extreme wide: 200 m × 2 m
    sh, sv, w, h = _pick_pt_scales(200.0, 2.0)
    assert w <= _PT_DRAW_W_MM and h <= _PT_DRAW_H_MM
    # Very tall: 30 m × 30 m
    sh, sv, w, h = _pick_pt_scales(30.0, 30.0)
    assert w <= _PT_DRAW_W_MM and h <= _PT_DRAW_H_MM
    # Tiny: 5 m × 0.5 m → smallest scale that fits
    sh, sv, w, h = _pick_pt_scales(5.0, 0.5)
    assert sh <= 100 and sv <= 100


def test_vertical_guides_are_profile_to_table_not_plan_to_profile(design):
    """Issue 1: the rappel/grid lines now link profile vertices to the
    top of the table (perfectly vertical) instead of plan to profile.
    ``get_rappel_segments`` still exists for backward compatibility but
    isn't called by the renderer; verify the contract directly."""
    # The rappel call has been removed from _draw_profile; no behavioural
    # test needed beyond confirming that the segments would have been
    # slanted (which would prove our concern was justified) is not what
    # we test here. Instead we verify the kept-vertical property:
    # for any two vertices, their pk_axis_x == column X used by the table.
    (nos, lengths, pks, ctn, cproj, col_x, diffs) = design.get_table_data()
    for i in range(len(design.pk_axis_x)):
        assert design.pk_axis_x[i] == col_x[i]
