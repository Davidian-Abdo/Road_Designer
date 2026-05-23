"""Sample-data + synthetic-terrain access for the CLI and the Streamlit UI.

Paths are resolved via ``importlib.resources`` so the package works regardless
of the current working directory — required by Streamlit Cloud (rule 9.2 in
CLAUDE.md).
"""
from __future__ import annotations

import io
from importlib import resources
from pathlib import Path
from typing import Tuple


def _samples_root() -> Path:
    """Resolve the project-level ``samples/`` folder (sibling of the package)."""
    # The package lives at <repo>/road_designer/, samples at <repo>/samples/.
    return (Path(__file__).resolve().parent.parent / "samples").resolve()


def sample_axe_path() -> Path:
    return _samples_root() / "sample_axe.txt"


def sample_terrain_path() -> Path:
    return _samples_root() / "sample_terrain.csv"


def sample_axe_bytes() -> bytes:
    return sample_axe_path().read_bytes()


def sample_terrain_bytes() -> bytes:
    return sample_terrain_path().read_bytes()


def generate_synthetic_terrain(
    axe_path: Path,
    out_path: Path,
    z_base: float = 780.0,
    slope_long: float = 0.02,
    amplitude: float = 4.0,
    wavelength: float = 600.0,
    noise_sigma: float = 0.4,
    extent: float = 60.0,
    perp_step: float = 5.0,
    pk_step: float = 5.0,
    seed: int = 42,
) -> Path:
    """Generate a synthetic TN CSV around ``axe_path``.

    The Streamlit UI calls this directly. Returns the output path.
    """
    # Import lazily so the CLI doesn't pay the cost at startup
    from samples.synth_terrain import SynthParams, generate

    params = SynthParams(
        z_base=z_base, slope_long=slope_long,
        amplitude=amplitude, wavelength=wavelength,
        noise_sigma=noise_sigma, extent=extent,
        perp_step=perp_step, pk_step=pk_step, seed=seed,
    )
    df = generate(axe_path, params)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path


def synthetic_terrain_bytes(axe_path: Path, **kwargs) -> bytes:
    """In-memory variant for the Streamlit downloader."""
    from samples.synth_terrain import SynthParams, generate

    params = SynthParams(**{
        k: v for k, v in kwargs.items()
        if k in SynthParams.__dataclass_fields__
    })
    df = generate(axe_path, params)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
