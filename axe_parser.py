import numpy as np
import re
from math import cos, sin, atan2, pi

class LineSegment:
    """Straight line segment."""
    def __init__(self, start, end, start_pk, end_pk):
        self.start = np.array(start, dtype=float)
        self.end = np.array(end, dtype=float)
        self.start_pk = start_pk
        self.end_pk = end_pk
        self.length = np.hypot(*(self.end - self.start))
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
        self.start_pk = start_pk
        self.end_pk = end_pk
        self.length = length

        # Vectors from center to start and end
        v_start = self.start - self.center
        v_end = self.end - self.center
        cross = v_start[0] * v_end[1] - v_start[1] * v_end[0]
        dot = v_start[0] * v_end[0] + v_start[1] * v_end[1]
        self.sweep = atan2(cross, dot)

        computed_length = abs(self.sweep) * abs(self.radius)
        if abs(computed_length - self.length) > 0.1:
            print(f"Warning: Arc length mismatch: computed={computed_length:.3f}, given={self.length:.3f}")

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
        else:
            return np.array([sin(angle), -cos(angle)])

    def normal_at_distance(self, d):
        dir_vec = self.direction_at_distance(d)
        return np.array([-dir_vec[1], dir_vec[0]])


class AlignmentParser:
    def __init__(self, filename):
        self.filename = filename
        self.segments = []
        self.station_points = []

    def parse(self):
        with open(self.filename, 'r') as f:
            lines = [line.rstrip('\n') for line in f if line.strip() != '']

        first = lines[0].split()
        if len(first) != 3:
            raise ValueError(f"First line must be PK, X, Y, got: {lines[0]}")
        start_pk = float(first[0])
        start_x = float(first[1])
        start_y = float(first[2])
        self.station_points.append((start_pk, start_x, start_y))

        idx = 1
        current_pk = start_pk
        current_point = (start_x, start_y)

        while idx < len(lines):
            line = lines[idx].strip()

            if line[0].upper() == 'D':
                idx += 1
                next_line = lines[idx].strip()
                next_parts = next_line.split()
                if len(next_parts) != 3:
                    raise ValueError(f"Expected station after D line, got: {next_line}")
                end_pk = float(next_parts[0])
                end_x = float(next_parts[1])
                end_y = float(next_parts[2])
                seg = LineSegment(current_point, (end_x, end_y), current_pk, end_pk)
                self.segments.append(seg)
                current_pk = end_pk
                current_point = (end_x, end_y)
                self.station_points.append((end_pk, end_x, end_y))
                idx += 1
                continue

            if line[0].upper() == 'C':
                params = {}
                for i in range(3):
                    if i >0 :
                        idx += 1
                    if idx >= len(lines):
                        raise ValueError("Unexpected end of file while reading curve parameters")
                    param_line = lines[idx].strip()
                    if 'XC' in param_line:
                        match = re.search(r'XC\s*=\s*([0-9.-]+)', param_line)
                        if match:
                            params['XC'] = float(match.group(1))
                    elif 'YC' in param_line:
                        match = re.search(r'YC\s*=\s*([0-9.-]+)', param_line)
                        if match:
                            params['YC'] = float(match.group(1))
                    elif 'R' in param_line:
                        match = re.search(r'R\s*=\s*([0-9.-]+)', param_line)
                        if match:
                            params['R'] = float(match.group(1))
                    else:
                        raise ValueError(f"Unexpected curve parameter line: {param_line}")
                idx += 1
                if idx >= len(lines):
                    raise ValueError("Unexpected end of file after curve parameters")
                next_line = lines[idx].strip()
                next_parts = next_line.split()
                if len(next_parts) != 3:
                    raise ValueError(f"Expected station after curve, got: {next_line}")
                end_pk = float(next_parts[0])
                end_x = float(next_parts[1])
                end_y = float(next_parts[2])
                if 'XC' not in params or 'YC' not in params or 'R' not in params:
                    raise ValueError(f"Missing curve parameters: {params}")
                xc = params['XC']
                yc = params['YC']
                radius = params['R']
                length = end_pk - current_pk
                seg = ArcSegment(current_point, (end_x, end_y), (xc, yc), radius, current_pk, end_pk, length)
                self.segments.append(seg)
                current_pk = end_pk
                current_point = (end_x, end_y)
                self.station_points.append((end_pk, end_x, end_y))
                idx += 1
                continue

            raise ValueError(f"Unexpected line format: {line}")

        return self.segments

    def sample_points(self, step):
        points = []
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