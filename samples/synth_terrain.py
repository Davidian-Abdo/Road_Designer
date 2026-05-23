"""Generate a synthetic terrain CSV from any axe file.

Use case
--------
A civil engineer wants to dry-run Road Designer V 1.0 without owning a DEM.
This script parses their axe and emits a plausible TN (terrain naturel) around
it as a CSV that ``TerrainModel`` can load.

The TN model is:

    Z(x, y) = Z_base
            + slope_long  × (PK − PK_0)             ← uphill / downhill trend
            + amplitude   × sin(2π PK / wavelength) ← rolling hills
            + amplitude_t × sin(2π t / wavelength_t)← cross-slope wave
            + N(0, noise_sigma)                      ← gaussian noise

where ``t`` is the perpendicular offset to the axis. Sampled on a regular grid
of ``2 × extent / step + 1`` perpendicular points at every ``pk_step`` along
the axis. The resulting cloud is wider than ``cross_section_extent`` so the
TIN can be queried without hitting the convex-hull fallback.

CLI
---
    python -m samples.synth_terrain --axe samples/sample_axe.txt \\
        --out samples/sample_terrain.csv --z-base 780 --slope 0.02 \\
        --amplitude 4 --wavelength 600 --noise 0.4
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Robust import whether called as a module or as a script
try:
    from road_designer.axe_parser import AlignmentParser
    from road_designer.geometry_engine import compute_normal
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from road_designer.axe_parser import AlignmentParser
    from road_designer.geometry_engine import compute_normal


@dataclass
class SynthParams:
    z_base: float = 780.0
    slope_long: float = 0.02            # 2 % grade along the axis
    amplitude: float = 4.0              # m, longitudinal rolling
    wavelength: float = 600.0           # m
    amplitude_t: float = 1.5            # m, cross-slope wave
    wavelength_t: float = 60.0          # m
    noise_sigma: float = 0.4            # m
    extent: float = 60.0                # ± m perpendicular sampling
    perp_step: float = 5.0              # m between perpendicular samples
    pk_step: float = 5.0                # m along the axis
    seed: int = 42


def generate(axe_path: Path, params: SynthParams) -> pd.DataFrame:
    """Return a DataFrame with columns X, Y, Z covering the corridor."""
    parser = AlignmentParser(axe_path)
    parser.parse()
    axis = parser.sample_points(params.pk_step)
    if not axis:
        raise ValueError("Empty axe — nothing to sample.")

    rng = np.random.default_rng(params.seed)
    pk0 = axis[0][0]

    n_t = int(np.floor(params.extent / params.perp_step))
    offsets = np.arange(-n_t, n_t + 1) * params.perp_step

    xs, ys, zs = [], [], []
    for i, (pk, x_ax, y_ax) in enumerate(axis):
        # Tangent direction at this axis point (numerical)
        if i + 1 < len(axis):
            x_n, y_n = axis[i + 1][1], axis[i + 1][2]
            dx, dy = x_n - x_ax, y_n - y_ax
        else:
            x_p, y_p = axis[i - 1][1], axis[i - 1][2]
            dx, dy = x_ax - x_p, y_ax - y_p
        normal = compute_normal(dx, dy)

        for t in offsets:
            xt = x_ax + normal[0] * t
            yt = y_ax + normal[1] * t
            zt = (
                params.z_base
                + params.slope_long * (pk - pk0)
                + params.amplitude * np.sin(2 * np.pi * pk / params.wavelength)
                + params.amplitude_t * np.sin(
                    2 * np.pi * t / params.wavelength_t
                )
                + rng.normal(0.0, params.noise_sigma)
            )
            xs.append(xt)
            ys.append(yt)
            zs.append(zt)

    return pd.DataFrame({"X": xs, "Y": ys, "Z": zs})


# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Generate a synthetic terrain CSV from an axe file."
    )
    ap.add_argument("--axe", required=True,
                    help="Path to the axe.txt to wrap with terrain.")
    ap.add_argument("--out", required=True,
                    help="Output CSV path.")
    ap.add_argument("--z-base", type=float, default=780.0)
    ap.add_argument("--slope", type=float, default=0.02,
                    help="Longitudinal grade (fraction, e.g. 0.02 = 2 %).")
    ap.add_argument("--amplitude", type=float, default=4.0,
                    help="Longitudinal rolling amplitude [m].")
    ap.add_argument("--wavelength", type=float, default=600.0,
                    help="Longitudinal rolling wavelength [m].")
    ap.add_argument("--noise", type=float, default=0.4,
                    help="Per-point gaussian noise sigma [m].")
    ap.add_argument("--extent", type=float, default=60.0,
                    help="Perpendicular sampling extent [± m].")
    ap.add_argument("--perp-step", type=float, default=5.0)
    ap.add_argument("--pk-step", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    params = SynthParams(
        z_base=args.z_base, slope_long=args.slope,
        amplitude=args.amplitude, wavelength=args.wavelength,
        noise_sigma=args.noise, extent=args.extent,
        perp_step=args.perp_step, pk_step=args.pk_step,
        seed=args.seed,
    )

    df = generate(Path(args.axe), params)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df):,} TN points to {out_path}")
    print(f"  Z range: [{df['Z'].min():.2f}, {df['Z'].max():.2f}] m")


if __name__ == "__main__":
    main()
