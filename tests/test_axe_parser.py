"""Tests for AlignmentParser — D + C grammar, station continuity, sampling."""
from __future__ import annotations

import math
import textwrap

import pytest

from road_designer.axe_parser import AlignmentParser, ArcSegment, LineSegment


# ─────────────────────────────────────────────────────────────────────────────
# Bundled sample
# ─────────────────────────────────────────────────────────────────────────────

def test_sample_axe_parses(axe_path):
    p = AlignmentParser(axe_path)
    segs = p.parse()
    assert len(segs) > 0
    # First station present
    assert len(p.station_points) == len(segs) + 1
    # Monotonic PK
    pks = [s.start_pk for s in segs] + [segs[-1].end_pk]
    assert all(b > a for a, b in zip(pks, pks[1:])), \
        "PKs must be strictly increasing"


def test_sample_axe_has_lines_and_arcs(axe_path):
    p = AlignmentParser(axe_path)
    segs = p.parse()
    n_lines = sum(1 for s in segs if isinstance(s, LineSegment))
    n_arcs = sum(1 for s in segs if isinstance(s, ArcSegment))
    assert n_lines > 0 and n_arcs > 0


def test_sample_continuity(axe_path):
    """End of segment i = start of segment i+1, to 1 mm."""
    p = AlignmentParser(axe_path)
    segs = p.parse()
    for a, b in zip(segs, segs[1:]):
        assert math.isclose(a.end[0], b.start[0], abs_tol=1e-3)
        assert math.isclose(a.end[1], b.start[1], abs_tol=1e-3)
        assert math.isclose(a.end_pk, b.start_pk, abs_tol=1e-3)


def test_sample_points_density(axe_path):
    p = AlignmentParser(axe_path)
    p.parse()
    pts = p.sample_points(step=1.0)
    pks = [pk for pk, _, _ in pts]
    assert pks == sorted(pks)
    # At step=1, no two adjacent points should be > 1.1 m apart in PK
    gaps = [b - a for a, b in zip(pks, pks[1:])]
    assert max(gaps) <= 1.2


# ─────────────────────────────────────────────────────────────────────────────
# Minimal hand-rolled axe — straight only
# ─────────────────────────────────────────────────────────────────────────────

def test_minimal_straight(tmp_path):
    axe = tmp_path / "axe.txt"
    axe.write_text(textwrap.dedent("""\
        0.0  0.0   0.0
        D1   GIS=0g   100.0
        100.0 100.0   0.0
    """))
    segs = AlignmentParser(axe).parse()
    assert len(segs) == 1
    assert isinstance(segs[0], LineSegment)
    assert math.isclose(segs[0].length, 100.0, abs_tol=1e-6)


def test_first_line_three_floats(tmp_path):
    axe = tmp_path / "axe.txt"
    axe.write_text("0.0  0.0\nD1   GIS=0g   1.0\n1.0  1.0  0.0\n")
    with pytest.raises(ValueError, match="PK X Y"):
        AlignmentParser(axe).parse()
