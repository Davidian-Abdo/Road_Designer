import numpy as np
import ezdxf
from ezdxf.math import Vec2
from ezdxf.enums import TextEntityAlignment
from config import *
from road_design import RoadDesign
from geometry_engine import compute_normal, cutting_line_points

def main():
    # 1. Create the road design object (all calculations)
    design = RoadDesign('terrain_database.csv', 'axe.txt')

    # 2. Create DXF document
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # ----- Plan View (rotated coordinates) -----
    # Axis and edges
    axis_rot = design.get_plan_axis()
    left_edges, right_edges = design.get_plan_edges()

    msp.add_lwpolyline([Vec2(x, y) for x, y in axis_rot],
                       dxfattribs={'color': 5, 'layer': 'AXIS'})
    msp.add_lwpolyline([Vec2(x, y) for x, y in left_edges],
                       dxfattribs={'color': 8, 'layer': 'EDGES'})
    msp.add_lwpolyline([Vec2(x, y) for x, y in right_edges],
                       dxfattribs={'color': 8, 'layer': 'EDGES'})

    # Arc annotations (ticks and curved arrows)
    for arc in design.get_arc_annotations():
        # Start tick
        if arc['start_xy_rot'] is not None and arc['start_tangent_rot'] is not None:
            x_rot, y_rot = arc['start_xy_rot']
            normal = np.array([-arc['start_tangent_rot'][1], arc['start_tangent_rot'][0]])
            p_tick1 = np.array([x_rot, y_rot]) + normal * (TICK_LENGTH / 2)
            p_tick2 = np.array([x_rot, y_rot]) - normal * (TICK_LENGTH / 2)
            msp.add_line(Vec2(p_tick1[0], p_tick1[1]), Vec2(p_tick2[0], p_tick2[1]),
                         dxfattribs={'color': 6, 'layer': 'TICKS'})
            text_pos = p_tick1 + normal * TICK_OFFSET
            msp.add_text(f"R={arc['radius']:.3f}", height=2.0,
                         dxfattribs={'color': 6, 'layer': 'TICKS'}).set_placement(
                             Vec2(text_pos[0], text_pos[1]), align=TextEntityAlignment.LEFT)

        # End tick
        if arc['end_xy_rot'] is not None and arc['end_tangent_rot'] is not None:
            x_rot, y_rot = arc['end_xy_rot']
            normal = np.array([-arc['end_tangent_rot'][1], arc['end_tangent_rot'][0]])
            p_tick1 = np.array([x_rot, y_rot]) + normal * (TICK_LENGTH / 2)
            p_tick2 = np.array([x_rot, y_rot]) - normal * (TICK_LENGTH / 2)
            msp.add_line(Vec2(p_tick1[0], p_tick1[1]), Vec2(p_tick2[0], p_tick2[1]),
                         dxfattribs={'color': 6, 'layer': 'TICKS'})
            text_pos = p_tick1 + normal * TICK_OFFSET
            msp.add_text(f"R={arc['radius']:.3f}", height=2.0,
                         dxfattribs={'color': 6, 'layer': 'TICKS'}).set_placement(
                             Vec2(text_pos[0], text_pos[1]), align=TextEntityAlignment.LEFT)

        # Curved arrow
        msp.add_lwpolyline([Vec2(x, y) for x, y in arc['arrow_points_rot']],
                           dxfattribs={'color': ARC_ARROW_COLOR, 'layer': 'ARC_ARROW'})
        msp.add_text(arc['label'], height=2.5,
                     dxfattribs={'color': ARC_ARROW_COLOR, 'layer': 'ARC_ARROW'}).set_placement(
                         Vec2(arc['midpoint_rot'][0], arc['midpoint_rot'][1]),
                         align=TextEntityAlignment.MIDDLE_CENTER)

    # Straight line annotations
    for line in design.get_line_annotations():
        offset_line = line['offset_line_rot']
        msp.add_line(Vec2(offset_line[0,0], offset_line[0,1]),
                     Vec2(offset_line[1,0], offset_line[1,1]),
                     dxfattribs={'color': STRAIGHT_ARROW_COLOR, 'layer': 'STRAIGHT_ARROW'})
        msp.add_text(line['label'], height=2.5,
                     dxfattribs={'color': STRAIGHT_ARROW_COLOR, 'layer': 'STRAIGHT_ARROW'}).set_placement(
                         Vec2(line['midpoint_rot'][0], line['midpoint_rot'][1]),
                         align=TextEntityAlignment.MIDDLE_CENTER)

    # Cutting lines and annotation bubbles at station vertices
    for i, (pk, x_rot, y_rot) in enumerate(zip(design.vert_pks, design.vert_x_rot, design.vert_y_rot)):
        if i == 0:
            dx = design.vert_x_rot[i+1] - x_rot
            dy = design.vert_y_rot[i+1] - y_rot
        elif i == len(design.vert_x_rot)-1:
            dx = x_rot - design.vert_x_rot[i-1]
            dy = y_rot - design.vert_y_rot[i-1]
        else:
            dx = design.vert_x_rot[i+1] - design.vert_x_rot[i-1]
            dy = design.vert_y_rot[i+1] - design.vert_y_rot[i-1]
        normal = compute_normal(dx, dy)

        p1, p2 = cutting_line_points(np.array([x_rot, y_rot]), normal, CUTTING_LINE_LENGTH)
        msp.add_line(Vec2(p1[0], p1[1]), Vec2(p2[0], p2[1]),
                     dxfattribs={'color': 6, 'layer': 'CUTTING_LINES'})

        bubble_center = np.array([x_rot, y_rot]) + normal * ANNOTATION_OFFSET
        msp.add_circle(center=Vec2(bubble_center[0], bubble_center[1]), radius=2.0,
                       dxfattribs={'color': 4, 'layer': 'BUBBLES'})
        msp.add_text(f"P{i+1}", height=2.0,
                     dxfattribs={'color': 4, 'layer': 'BUBBLES'}).set_placement(
                         Vec2(bubble_center[0], bubble_center[1]),
                         align=TextEntityAlignment.MIDDLE_CENTER)

    # ----- Profile View --------------
    prof_x, ground_y, proj_y, prof_x_dense, proj_y_dense,profile_base_y = design.get_profile_data()
    profile_nos, lengths, pks, cote_tn, cote_proj, col_x, diffs = design.get_table_data()
    
    # Ground line (green) 
    msp.add_lwpolyline([Vec2(x, y) for x, y in zip(prof_x, ground_y)],
                       dxfattribs={'color': 3, 'layer': 'GROUND'})
    # Project line (red)
    msp.add_lwpolyline([Vec2(x, y) for x, y in zip(prof_x_dense, proj_y_dense)],
                       dxfattribs={'color': 1, 'layer': 'PROJECT'})

    # Rappel lines (connecting plan to profile) – these will be slanted
    # We iterate through vertices only to avoid "clutter" and slanted lines
    for i in range(len(design.vert_x_rot)):
        x_pos = design.vert_x_rot[i]
        y_plan = design.vert_y_rot[i]
        y_ground_prof = ground_y[i]
    
        # Draw the vertical Rappel line
        msp.add_line(Vec2(x_pos, y_plan), Vec2(x_pos, y_ground_prof),
                 dxfattribs={'color': 2, 'linetype': 'DASHED', 'layer': 'RAPPEL'})

        # FIX: Adding the Cut/Fill Labels (Professional BET Style)
        h_val = diffs[i]
        if abs(h_val) > 0.01:  # Don't write 0.000
            label = f"{'Remb' if h_val > 0 else 'Déb'}={abs(h_val):.2f}m"
            color = 1 if h_val < 0 else 3 # Red for Cut, Green for Fill (optional)
        
            # Calculate text position: midpoint between TN and Project
            # We query the project height at this specific vertex
            vert_proj_y = profile_base_y + (float(cote_proj[i]) - design.datum) * V_SCALE
            text_y = vert_proj_y + 0.5
        
            txt = msp.add_text(label, height=1.5, 
                           dxfattribs={'color': color, 'layer': 'HAUTEURS'})
        
            # Professional vertical orientation (90 degrees)
            txt.set_placement(Vec2(x_pos + 0.5, text_y), # Offset 0.5m to the right of line
                          align=TextEntityAlignment.MIDDLE_CENTER)
            txt.dxf.rotation = 45

    # ----- Table with 5 rows, columns aligned with profile X positions -----
    table_y = profile_base_y - 5.0

    margin = 10.0
    x_min = min(col_x) - margin
    x_max = max(col_x) + margin

    
    row_heights = [5.0, 5.0, 15.0, 15.0, 15.0]
    table_top = table_y
    table_bottom = table_top - sum(row_heights)

    CURV_DIAG_ROW_HEIGHT= 8
    y_diag_top = table_bottom
    y_diag_bottom = y_diag_top - CURV_DIAG_ROW_HEIGHT # Make this row taller (e.g., 10 units)
    # Outer vertical boundaries
    msp.add_line(Vec2(x_min, table_top), Vec2(x_min, table_bottom), dxfattribs={'color': 7, 'layer': 'TABLE'})
    msp.add_line(Vec2(x_max, table_top), Vec2(x_max, table_bottom), dxfattribs={'color': 7, 'layer': 'TABLE'})

    # Vertical lines at each vertex (using scaled PK positions)
    for x in col_x:
        msp.add_line(Vec2(x, table_top), Vec2(x, table_bottom), dxfattribs={'color': 7, 'layer': 'TABLE'})

    # Horizontal lines for rows
    current_y = table_top
    row_y_positions = [table_top]
    for h in row_heights:
        current_y -= h
        row_y_positions.append(current_y)
    # Draw horizontal lines
    for y in row_y_positions:
        msp.add_line(Vec2(x_min, y), Vec2(x_max, y), dxfattribs={'color': 7})

    # Define Title Column Width
    title_width = 30.0
    x_title_start = x_min - title_width

    # Row Names mapping
    row_labels = [
        "Numéro du Profil",
        "Distances Partielles",
        "Distances Cumulées (PK)",
        "Cotes TN",
        "Cotes Projet",
        "Pentes et Rampes"
    ]

    # Draw the Title Box and horizontal separators
    for i, label in enumerate(row_labels):
        y_row_top =  row_y_positions[i]
        y_row_bottom = row_y_positions[i+1] if i < 5 else row_y_positions[i]-CURV_DIAG_ROW_HEIGHT
        
        # Draw box for the title
        msp.add_line(Vec2(x_title_start, y_row_top), Vec2(x_min, y_row_top), dxfattribs={'color': 7})
        
        # Add Label Text
        msp.add_text(label, height=1.8, dxfattribs={'color': 7}).set_placement(
            Vec2(x_title_start + 1, (y_row_top + y_row_bottom) / 2),
            align=TextEntityAlignment.MIDDLE_LEFT)

    # Close the left side of the title block
    msp.add_line(Vec2(x_title_start, table_top), Vec2(x_title_start, y_diag_bottom), dxfattribs={'color': 7})

    # Fill data
    for col, (x_pos, pno, length, pk, tn, proj) in enumerate(zip( 
            col_x, profile_nos, lengths, pks, cote_tn, cote_proj)):
        
        # Row 0: Profile No
        msp.add_text(pno, height=3.0, dxfattribs={'color': 7, 'layer': 'TABLE_TEXT'}).set_placement(
            Vec2(x_pos + 3, row_y_positions[0] - 2.5), align=TextEntityAlignment.MIDDLE_CENTER)
        
        # Row 1: Length
        if col < len(col_x) - 1:
            next_x = col_x[col + 1]
            mid_block_x= (x_pos + next_x) / 2
            seg_length = lengths[col+1]
            msp.add_text(seg_length, height=2.5, dxfattribs={'color': 7, 'layer': 'TABLE_TEXT'}).set_placement(
                Vec2(mid_block_x, row_y_positions[1] - 2.5), align=TextEntityAlignment.MIDDLE_CENTER)
        # Row 2: PK
        t2 = msp.add_text(pk, height=1.8, dxfattribs={'layer': 'TABLE_TEXT'})
        t2.set_placement(Vec2(x_pos + 1, row_y_positions[2] - 7.5), align=TextEntityAlignment.MIDDLE_CENTER)
        t2.dxf.rotation = 90
        # Row 3: Cote TN (Vertical, 90 deg, offset from line)
        t3 = msp.add_text(tn, height=1.8)
        t3.set_placement(Vec2(x_pos + 0.6, row_y_positions[3] - 7.5), align=TextEntityAlignment.MIDDLE_CENTER)
        t3.dxf.rotation = 90

        # Row 4: Cote Projet (Vertical, 90 deg, offset from line)
        t4 = msp.add_text(proj, height=1.8)
        t4.set_placement(Vec2(x_pos + 0.6, row_y_positions[4] - 7.5), align=TextEntityAlignment.MIDDLE_CENTER)
        t4.dxf.rotation = 90


    # Row 5: Diagramme des Courbures
    y_mid = (y_diag_top + y_diag_bottom) / 2

    # Draw the baseline
    msp.add_line(Vec2(x_min, y_diag_bottom), Vec2(x_max, y_diag_bottom), dxfattribs={'color': 7, 'linetype': 'CENTER','layer': 'TABLE'})

    # We need to build a continuous sequence of Tangent -> Curve -> Tangent
    segments = []
    last_pk = design.v_align.pvi[0, 0] 
    
    for curve in design.v_align.curves:
        # Add the tangent before the curve
        if curve['start'] > last_pk:
            segments.append({
                'type': 'STR',
                'start': last_pk,
                'end': curve['start'],
                'grade': design.v_align.grades[curve['pvi_idx']-1]
            })
        # Add the curve itself
        segments.append({
            'type': 'ARC',
            'start': curve['start'],
            'end': curve['end'],
            'radius': curve['R'], # Simplified representation of R
            'sign': curve['sign'], # 1.0 for Sag/Cuvette, -1.0 for Summit/Sommet
            'g1': curve['g1'],
            'g2': design.v_align.grades[curve['pvi_idx']]
        })
        last_pk = curve['end']
    
    # Add final tangent
    final_pk = design.v_align.pvi[-1, 0]
    if last_pk < final_pk:
        segments.append({
            'type': 'STR',
            'start': last_pk,
            'end': final_pk,
            'grade': design.v_align.grades[-1]
        })

    # --- Step C: Draw the Segments and Labels ---
    for seg in segments: 
        s_x = design.pk_to_x_rot(seg['start'])
        e_x = design.pk_to_x_rot(seg['end'])
        mid_x = (s_x + e_x) / 2
        length = seg['end'] - seg['start']

        # 1. Independent Column Separator (Lines only in Row 5)
        msp.add_line(Vec2(s_x, y_diag_top), Vec2(s_x, y_diag_bottom), dxfattribs={'color': 7})
        msp.add_line(Vec2(e_x, y_diag_top), Vec2(e_x, y_diag_bottom), dxfattribs={'color': 7})

        if seg['type'] == 'STR':
            pente = seg['grade']
            # Draw slanted line based on slope direction
            # From 1/4 height to 3/4 height to keep it inside the box
            y1 = y_diag_bottom + 2 if pente > 0 else y_diag_top - 2
            y2 = y_diag_top - 2 if pente > 0 else y_diag_bottom + 2
            msp.add_line(Vec2(s_x, y1), Vec2(e_x, y2), dxfattribs={'color': 1}) # Red for project
            
            # Professional Labels: Pente % and Length
            msp.add_text(f"P={pente*100:.2f}%", height=1.5).set_placement(
                Vec2(mid_x, y_mid + 1), align=TextEntityAlignment.MIDDLE_CENTER)
            msp.add_text(f"L={length:.2f}m", height=1.2).set_placement(
                Vec2(mid_x, y_mid - 2), align=TextEntityAlignment.MIDDLE_CENTER)

        else:
            # Draw Parabolic Arc (Summit vs Sag)
            is_sag = seg['sign'] > 0 # Cuvette
            pts = []
            for t in np.linspace(0, 1, 10):
                curr_x = s_x + (e_x - s_x) * t
                # Parabolic bulge calculation
                h = 4 * t * (1 - t) * (CURV_DIAG_ROW_HEIGHT * 0.4)
                curr_y = (y_diag_bottom + h) if not is_sag else (y_diag_top - h)
                pts.append(Vec2(curr_x, curr_y))
            
            msp.add_lwpolyline(pts, dxfattribs={'color': 4}) # Cyan for curves
            
            # Professional Labels: R (Radius) and L (Length)
            # R is derived from K-value: R = K * 100 (approx) or use K directly
            radius_val = abs(seg['radius']) 
            label_y = y_diag_top + 1.5 if not is_sag else y_diag_bottom - 2.5
            
            msp.add_text(f"R={radius_val:.0f}", height=1.5).set_placement(
                Vec2(mid_x, label_y), align=TextEntityAlignment.MIDDLE_CENTER)
            msp.add_text(f"L={length:.2f}m", height=1.2).set_placement(
                Vec2(mid_x, y_mid), align=TextEntityAlignment.MIDDLE_CENTER)

            
    # Save
    doc.saveas('road_design.dxf')
    print("DXF generated: road_design.dxf")

if __name__ == '__main__':
    main()