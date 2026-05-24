"""Layout regression tests — bug C8 must not come back.

Bug C8 (May 2026): the profile was rendered at PK coordinates (0..L) while
the plan lived in rotated Lambert coordinates (~10⁵), pushing the profile
hundreds of kilometres away and turning rappel lines into near-horizontal
strokes. The fix anchors the profile X to ``vert_x_rot[0]`` and places the
profile baseline below the plan with proper clearance.

These tests pin the contract.
"""
from __future__ import annotations

import math


def test_profile_x_anchored_to_first_plan_vertex(design):
    """First profile column shares the rotated X of the first plan vertex."""
    assert math.isclose(design.pk_axis_x[0], design.vert_x_rot[0],
                        abs_tol=1e-6)


def test_profile_x_monotonic_in_pk(design):
    """C1 must keep holding — PK ↑ ⇒ profile X ↑."""
    for a, b in zip(design.pk_axis_x, design.pk_axis_x[1:]):
        assert b > a


def test_profile_x_within_or_near_plan_x(design):
    """Profile span should overlap with the plan span — never thousands
    of metres away. Allow profile to extend up to 2× the plan width to
    the right (winding roads unfold)."""
    plan_xmin, plan_xmax = design.vert_x_rot.min(), design.vert_x_rot.max()
    plan_width = plan_xmax - plan_xmin
    prof_xmin, prof_xmax = design.pk_axis_x.min(), design.pk_axis_x.max()
    # Same start, allowable right-extension
    assert math.isclose(prof_xmin, plan_xmin, abs_tol=1e-6)
    assert prof_xmax <= plan_xmax + 2 * plan_width


def test_profile_below_plan_with_clearance(design):
    """Profile TN line should sit below the plan with at least
    ``cfg.profile_gap_d`` of clearance — and never above the plan."""
    cfg = design.cfg
    ground_y_max = (design.profile_base_y
                    + (design.vert_ground_z.max() - design.datum)
                    * cfg.v_scale)
    proj_y_max = (design.profile_base_y
                  + (design.dense_proj_z.max() - design.datum)
                  * cfg.v_scale)
    profile_top_y = max(ground_y_max, proj_y_max)
    plan_bottom_y = float(design.vert_y_rot.min())
    assert profile_top_y <= plan_bottom_y + 1e-3, \
        f"Profile overlaps plan: profile_top={profile_top_y:.2f}, " \
        f"plan_bottom={plan_bottom_y:.2f}"
    clearance = plan_bottom_y - profile_top_y
    assert clearance >= cfg.profile_gap_d - 1e-3, \
        f"Clearance {clearance:.2f} < requested {cfg.profile_gap_d:.2f}"


def test_rappel_lines_nearly_vertical(design):
    """For our sample (~1 km road), rappel lines must drop nearly straight
    down — their horizontal span at the start must be 0 and never exceed
    the road length."""
    rappels = design.get_rappel_segments()
    (x_plan_first, _), (x_prof_first, _) = rappels[0]
    assert math.isclose(x_plan_first, x_prof_first, abs_tol=1e-6)
    L = float(design.vert_pks[-1] - design.vert_pks[0])
    for (x_plan, _), (x_prof, _) in rappels:
        assert abs(x_prof - x_plan) <= L + 1e-6
