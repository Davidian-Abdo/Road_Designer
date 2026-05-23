import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree

class TerrainModel:
    """Loads a CSV (X,Y,Z) and builds a continuous surface using linear TIN interpolation.
    Falls back to nearest neighbor if query point is outside convex hull.
    """
    def __init__(self, csv_file):
        self.data = pd.read_csv(csv_file)
        self.points = self.data[['X', 'Y']].values
        self.z = self.data['Z'].values
        self.interpolator = LinearNDInterpolator(self.points, self.z)
        # Build KDTree for nearest neighbor fallback
        self.tree = cKDTree(self.points)

    def query_z(self, x, y):
        """Return interpolated Z at (x,y). If outside convex hull, returns nearest point's Z."""
        z = self.interpolator(x, y)
        if np.isnan(z):
            # Fallback to nearest neighbor
            dist, idx = self.tree.query([x, y])
            z = self.z[idx]
            print(f"Warning: Point ({x:.3f}, {y:.3f}) outside terrain convex hull, using nearest neighbor Z={z:.3f}")
        return z