# design_logic.py
import numpy as np

class VerticalAlignment:
    """
    Standard Road Engineering Ligne Rouge.
    Uses Parabolic transitions with per‑curve radius selection.
    """
    def __init__(self, pvi_list, min_summit, min_sag, safety_factor=0.95,
                 target_mode='max', desired_radius=None,max_radius=None):
        """
        Parameters
        ----------
        pvi_list : array-like of [PK, elevation]
        min_summit : float – minimum radius for summit curves (Δg < 0)
        min_sag : float – minimum radius for sag curves (Δg > 0)
        safety_factor : float – fraction of the available length to use (default 0.95)
        target_mode : str – 'max' or 'fixed'
        desired_radius : float or list, optional – target radius(s) for 'fixed' mode
        """
        self.pvi = np.array(pvi_list)
        self.max_radius = max_radius
        self.min_summit = min_summit
        self.min_sag = min_sag
        self.safety_factor = safety_factor
        self.target_mode = target_mode
        self.desired_radius = desired_radius
        self._compute_curves()

    def _compute_curves(self):
        n = len(self.pvi)
        # Compute grades between consecutive PVIs
        self.grades = []
        for i in range(n-1):
            dz = self.pvi[i+1, 1] - self.pvi[i, 1]
            dpk = self.pvi[i+1, 0] - self.pvi[i, 0]
            self.grades.append(dz / dpk if dpk != 0 else 0.0)

        self.curves = []
        for i in range(1, n-1):
            g1 = self.grades[i-1]
            g2 = self.grades[i]
            delta_g = g2 - g1
            abs_dg = abs(delta_g)
            if abs_dg < 1e-6:
                continue   # no grade change → no curve

            pk_pvi = self.pvi[i, 0]

            # Distances to adjacent PVIs
            dist_prev = pk_pvi - self.pvi[i-1, 0]
            dist_next = self.pvi[i+1, 0] - pk_pvi

            # Maximum curve length that can fit without overlapping
            L_max = min(dist_prev, dist_next)
            L_max_allowed = L_max * self.safety_factor

            # Corresponding maximum radius from L = R * |Δg|
            R_max = L_max_allowed / abs_dg

            # Choose radius according to mode
            if self.target_mode == 'max':
                R = R_max
            elif self.target_mode == 'fixed':
                if self.desired_radius is not None:
                    if isinstance(self.desired_radius, (list, tuple)):
                        # Assume list corresponds to interior PVIs in order
                        des = self.desired_radius[i-1]
                    else:
                        des = self.desired_radius
                    R = min(des, R_max)
                else:
                    R = R_max   # fallback
            else:
                R = R_max       # default

            if self.max_radius is not None:
                R = min(R, self.max_radius) 

            # Apply minimum radius based on curve type
            if delta_g > 0:          # sag (cuvette)
                min_rad = self.min_sag
            else:                     # summit (sommet)
                min_rad = self.min_summit

            if R < min_rad:
                print(f"Warning: PVI at PK {pk_pvi:.3f} requires radius {R:.0f} m "
                      f"which is below minimum {min_rad} m. ")
                R=min_rad

            # Actual curve length
            L = abs_dg * R

            self.curves.append({
                'start': pk_pvi - L/2,
                'end': pk_pvi + L/2,
                'R': R,
                'L': L,
                'pvi_idx': i,
                'g1': g1,
                'sign': 1.0 if delta_g > 0 else -1.0
            })

    def get_z(self, pk):
        """Return project elevation at given PK."""
        if pk <= self.pvi[0, 0]:
            return self.pvi[0, 1]
        if pk >= self.pvi[-1, 0]:
            return self.pvi[-1, 1]

        # Check if inside a vertical curve
        for c in self.curves:
            if c['start'] <= pk <= c['end']:
                x = pk - c['start']
                g1 = c['g1']
                g2 = self.grades[c['pvi_idx']]
                L = c['L']
                # Elevation of the PVC
                pvi_pk, pvi_z = self.pvi[c['pvi_idx']]
                y_pvc = pvi_z - (g1 * (L / 2.0))
                # Parabolic formula
                return y_pvc + (g1 * x) + ((g2 - g1) / (2 * L)) * (x**2)

        # Linear interpolation between PVIs
        for i in range(len(self.pvi)-1):
            if self.pvi[i, 0] <= pk <= self.pvi[i+1, 0]:
                return self.pvi[i, 1] + self.grades[i] * (pk - self.pvi[i, 0])

        return self.pvi[-1, 1]