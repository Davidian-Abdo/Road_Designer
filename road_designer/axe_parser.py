"""Parser for the Moroccan-style axe file (segments droits D + courbes C).

File grammar
------------
First line:   PK0   X0   Y0
Then repeating blocks:
  - Straight (segment droit):
        D{n}    GIS = ...   length
        PK   X   Y                          ← end-of-segment station

  - Arc (courbe circulaire):
        C{n}    XC = xc
                YC = yc
                R = radius   length         ← signed radius (+/- = direction)
        PK   X   Y                          ← end-of-arc station

Radii are signed in the input: positive = curve turning left, negative = right.
"""
from __future__ import annotations

import re
from math import atan2, cos, pi, sin
from pathlib import Path
from typing import List, Tuple, Union

import numpy as np


class LineSegment:
    """Straight segment between two stations."""

    def __init__(self, start, end, start_pk, end_pk):
        self.start = np.array(start, dtype=float)
        self.end = np.array(end, dtype=float)
        self.start_pk = float(start_pk)
        self.end_pk = float(end_pk)
        self.length = float(np.hypot(*(self.end - self.start)))
        if self.length == 0:
            raise ValueError(
                f"Zero-length straight at PK {self.start_pk}"
            )
        self.direction = (self.end - self.start) / self.length

    def point_at_distance(self, d):
        return self.start + self.direction * d

    def direction_at_distance(self, d):
        return self.direction

    def normal_at_distance(self, d):
        return np.array([-self.direction[1], self.direction[0]])


class ArcSegment:
    """Circular arc segment."""

    def __init__(self, start, end, center, radius, start_pk, end_pk, length):
        self.start = np.array(start, dtype=float)
        self.end = np.array(end, dtype=float)
        self.center = np.array(center, dtype=float)
        self.radius = float(radius)
        self.start_pk = float(start_pk)
        self.end_pk = float(end_pk)
        self.length = float(length)

        v_start = self.start - self.center
        v_end = self.end - self.center
        cross = v_start[0] * v_end[1] - v_start[1] * v_end[0]
        dot = v_start[0] * v_end[0] + v_start[1] * v_end[1]
        self.sweep = atan2(cross, dot)

        computed_length = abs(self.sweep) * abs(self.radius)
        if abs(computed_length - self.length) > 0.1:
            print(
                f"Warning: arc length mismatch at PK {self.start_pk}: "
                f"computed={computed_length:.3f}, given={self.length:.3f}"
            )

        self.start_angle = atan2(v_start[1], v_start[0])
        self.end_angle = self.start_angle + self.sweep

    def point_at_distance(self, d):
        frac = d / self.length
        angle = self.start_angle + frac * self.sweep
        return self.center + abs(self.radius) * np.array([cos(angle), sin(angle)])

    def direction_at_distance(self, d):
        frac = d / self.length
        angle = self.start_angle + frac * self.sweep
        if self.sweep > 0:
            return np.array([-sin(angle), cos(angle)])
        return np.array([sin(angle), -cos(angle)])

    def normal_at_distance(self, d):
        dir_vec = self.direction_at_distance(d)
        return np.array([-dir_vec[1], dir_vec[0]])


# ─────────────────────────────────────────────────────────────────────────────

class AlignmentParser:
    """Parse a Moroccan-style axe file into a list of segments + stations."""

    def __init__(self, filename: Union[str, Path]):
        self.filename = Path(filename)
        self.segments: List = []
        self.station_points: List[Tuple[float, float, float]] = []

    # ------------------------------------------------------------------ API

    def parse(self):
        with open(self.filename, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f if ln.strip() != ""]

        first = lines[0].split()
        if len(first) != 3:
            raise ValueError(
                f"First line must be 'PK X Y' but got: {lines[0]!r}"
            )
        start_pk, start_x, start_y = (float(v) for v in first)
        self.station_points.append((start_pk, start_x, start_y))

        idx = 1
        current_pk = start_pk
        current_point = (start_x, start_y)

        while idx < len(lines):
            line = lines[idx].strip()

            # ── Straight ──────────────────────────────────────────
            if line[0].upper() == "D":
                idx += 1
                next_line = lines[idx].strip()
                parts = next_line.split()
                if len(parts) != 3:
                    raise ValueError(
                        f"Expected PK X Y after D line, got: {next_line!r}"
                    )
                end_pk, end_x, end_y = (float(v) for v in parts)
                seg = LineSegment(current_point, (end_x, end_y),
                                  current_pk, end_pk)
                self.segments.append(seg)
                current_pk, current_point = end_pk, (end_x, end_y)
                self.station_points.append((end_pk, end_x, end_y))
                idx += 1
                continue

            # ── Arc ──────────────────────────────────────────────
            if line[0].upper() == "C":
                params: dict = {}
                for i in range(3):
                    if i > 0:
                        idx += 1
                    if idx >= len(lines):
                        raise ValueError(
                            "Unexpected EOF inside curve parameters"
                        )
                    pl = lines[idx].strip()
                    if "XC" in pl:
                        m = re.search(r"XC\s*=\s*([0-9.\-]+)", pl)
                        if m: params["XC"] = float(m.group(1))
                    elif "YC" in pl:
                        m = re.search(r"YC\s*=\s*([0-9.\-]+)", pl)
                        if m: params["YC"] = float(m.group(1))
                    elif "R" in pl:
                        m = re.search(r"R\s*=\s*([0-9.\-]+)", pl)
                        if m: params["R"] = float(m.group(1))
                    else:
                        raise ValueError(
                            f"Unexpected curve parameter line: {pl!r}"
                        )

                idx += 1
                if idx >= len(lines):
                    raise ValueError("Unexpected EOF after curve parameters")
                next_line = lines[idx].strip()
                parts = next_line.split()
                if len(parts) != 3:
                    raise ValueError(
                        f"Expected PK X Y after curve, got: {next_line!r}"
                    )
                end_pk, end_x, end_y = (float(v) for v in parts)
                missing = {"XC", "YC", "R"} - set(params)
                if missing:
                    raise ValueError(f"Curve missing parameters: {missing}")

                length = end_pk - current_pk
                seg = ArcSegment(current_point, (end_x, end_y),
                                 (params["XC"], params["YC"]),
                                 params["R"], current_pk, end_pk, length)
                self.segments.append(seg)
                current_pk, current_point = end_pk, (end_x, end_y)
                self.station_points.append((end_pk, end_x, end_y))
                idx += 1
                continue

            raise ValueError(f"Unexpected line format: {line!r}")

        return self.segments

    def sample_points(self, step: float) -> List[Tuple[float, float, float]]:
        """Return list of (PK, X, Y) sampled along all segments at ``step`` m."""
        points: List[Tuple[float, float, float]] = []
        for seg in self.segments:
            num = int(np.ceil(seg.length / step)) + 1
            for k in range(num):
                d = min(k * step, seg.length)
                pk = seg.start_pk + d
                pt = seg.point_at_distance(d)
                points.append((pk, pt[0], pt[1]))
        unique = []
        last_pk = None
        for pk, x, y in points:
            if last_pk is None or abs(pk - last_pk) > 1e-6:
                unique.append((pk, x, y))
                last_pk = pk
        return unique
