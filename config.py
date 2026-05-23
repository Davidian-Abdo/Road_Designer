# config.py
ROAD_WIDTH = 7.0            # total width [m]
V_EXAG = 10                  # vertical exaggeration (for profile) - kept for reference
H_SCALE = 1          # horizontal scale 1:1000
V_SCALE = 10              # vertical scale (exaggeration factor)
R_SUMMIT = 1500           # K value for summit curves (Moroccan standard)
R_SAG = 1000             # K value for sag curves
max_radius = 6000
PROFILE_SAMPLING = 1.0       # sampling interval along alignment [m]
CUTTING_LINE_LENGTH = 10.0   # length of cutting lines in plan [m]
ANNOTATION_OFFSET = 15.0      # distance from axis to annotation bubble [m]

smothing_factor=0.13 # between 0 and 1 , smaller --> smother
# Parameters for arc endpoint ticks
TICK_LENGTH = 30.0           # length of perpendicular tick at arc endpoints [m]
TICK_OFFSET = 2.0            # extra offset for radius text beyond tick end [m]

# Parameters for arc arrow annotation
ARC_ARROW_STEPS = 20         # number of segments to draw the curved arrow
ARC_ARROW_COLOR = 4          # cyan (AutoCAD color index)
ARC_ARROW_OFFSET = 15.0      # distance outward from the road axis for the arrow [m]

# Parameters for straight segment annotation
STRAIGHT_ARROW_OFFSET = 15.0 # distance from the road axis for straight length arrow [m]
STRAIGHT_ARROW_COLOR = 4     # cyan

# Profile placement
PROFILE_GAP_D = 100.0        # fixed vertical distance between top of plan view and profile baseline [m]

# config.py updates
SMOOTHING_WINDOW = 10        # Number of stations to average (Higher = flatter road)
MIN_TANGENT_LENGTH = 120.0 # Minimum distance between two PVIs [m]
MIN_CURVE_LENGTH = 25.0
MAX_GRADE_CHANGE = 0.005    # 0.5% - Only create a PVI if grade change exceeds this

CURVATURE_DIAGRAM_HEIGHT = 4.0  # Total height of the row
CURVATURE_SCALE = 500.0         # Scaling factor for the humps

# Moroccan REFT Standards for Category 1 Roads (approx 80-100 km/h)
R_MIN_SOMMET_ABSOLU = 1500  # Absolute minimum
R_MIN_SOMMET_NORMAL = 3000  # Normal minimum
R_MIN_CUVETTE_ABSOLU = 750   # Absolute minimum
R_MIN_CUVETTE_NORMAL = 1500  # Normal minimum

MAX_PENTE = 6.0              # Max slope in % for mountainous terrain (varies)