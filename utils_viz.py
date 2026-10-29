#   ##########################################################
#   By Eugene Ch'ng
#   LinkedIn: https://www.linkedin.com/in/eugenecc/
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   360 CAMERA RIG VISUALISATION
#   ----------------------------------------------------------
#   Generates an interactive 3D visualisation of the camera
#   views extracted from an equirectangular 360-degree video
#
#   Displays horizontal, 45-degree and zenith camera views
#   Shows the field of view, image planes and view directions
#
#   Note that this function visualises the camera layout only
#   and does not perform image or video extraction
#   ##########################################################

import numpy as np
import plotly.graph_objects as go
from utils_ffmpeg import build_camera_views, normalise_yaw_degrees

def generate_360_splits(
    EXTRACT_EVERY_N_SECONDS=2,
    HORIZONTAL_SPLITS=8,
    INCLUDE_NADIR_ZENITH=True,
    INCLUDE_45_PITCH=True,
    FIELD_OF_VIEW=90,
    IMAGE_RESOLUTION=1024,
    HORIZONTAL_COVERAGE="full_360",
    FRONT_YAW_DEGREES=0,
    HORIZONTAL_COVERAGE_DEGREES=180,
):
    """
    Renders an interactive 3D visualization of the camera rig layout.
    """
    if HORIZONTAL_COVERAGE == "full_360":
        HORIZONTAL_COVERAGE_DEGREES = 360

    # --------------------------- CREATE 3D FIGURE
    # initialise an empty Plotly figure for the camera rig
    fig = go.Figure()

    # --------------------------- DRAW XYZ AXES
    # create the reference axes for forward, left and upward directions
    axis_range = 2.5
    fig.add_trace(go.Scatter3d(x=[-axis_range, axis_range], y=[0, 0], z=[0, 0], mode='lines+text',
                               line=dict(color='gray', width=4), text=['', '+X (Forward)'], textposition='bottom right', name='X Axis'))
    fig.add_trace(go.Scatter3d(x=[0, 0], y=[-axis_range, axis_range], z=[0, 0], mode='lines+text',
                               line=dict(color='gray', width=4), text=['', '+Y (Left)'], textposition='bottom right', name='Y Axis'))
    fig.add_trace(go.Scatter3d(x=[0, 0], y=[0, 0], z=[-axis_range, axis_range], mode='lines+text',
                               line=dict(color='gray', width=4), text=['', '+Z (Up)'], textposition='bottom right', name='Z Axis'))

    # --------------------------- DRAW 360 SPHERE
    # create a transparent unit sphere representing the 360-degree environment
    u = np.linspace(0, 2 * np.pi, 50)
    v = np.linspace(0, np.pi, 50)
    x = np.outer(np.cos(u), np.sin(v))
    y = np.outer(np.sin(u), np.sin(v))
    z = np.outer(np.ones(np.size(u)), np.cos(v))
    fig.add_trace(go.Surface(x=x, y=y, z=z, opacity=0.15, colorscale='Blues', showscale=False, name='360 Sphere'))

    # --------------------------- CREATE VIEW LAYOUT
    # Use the same view builder as the FFmpeg extraction pipeline so the
    # visualisation always matches the files that will be produced.
    camera_views = build_camera_views(
        HORIZONTAL_SPLITS,
        INCLUDE_NADIR_ZENITH,
        INCLUDE_45_PITCH,
        HORIZONTAL_COVERAGE,
        FRONT_YAW_DEGREES,
        HORIZONTAL_COVERAGE_DEGREES,
        FIELD_OF_VIEW,
    )
    views = [(view["yaw"], view["pitch"]) for view in camera_views]

    # Draw the user-defined front direction and its exact opposite. These are
    # references within the stitched MP4, not automatically detected lenses.
    front_yaw = np.radians(normalise_yaw_degrees(FRONT_YAW_DEGREES))
    reference_length = 2.1
    front_x = reference_length * np.cos(front_yaw)
    front_y = reference_length * np.sin(front_yaw)
    fig.add_trace(go.Scatter3d(
        x=[0, front_x], y=[0, front_y], z=[0, 0], mode="lines+text",
        line=dict(color="cyan", width=7), text=["", "Front reference"],
        textposition="top center", name="Front reference"
    ))
    fig.add_trace(go.Scatter3d(
        x=[0, -front_x], y=[0, -front_y], z=[0, 0], mode="lines+text",
        line=dict(color="orange", width=7), text=["", "Back reference"],
        textposition="top center", name="Back reference"
    ))

    # --------------------------- CALCULATE IMAGE PLANE
    # convert the field of view from degrees into radians
    fov_rad = np.radians(FIELD_OF_VIEW)

    # set the distance between the camera origin and image plane
    frame_distance = 1.2

    # calculate half the image plane size using the field of view
    half_size = frame_distance * np.tan(fov_rad / 2)

    # --------------------------- PLOT CAMERA VIEWS
    # calculate and draw the image plane for every camera direction
    for i, (yaw, pitch) in enumerate(views):

        # convert yaw and pitch angles from degrees into radians
        yaw_rad = np.radians(yaw)
        pitch_rad = np.radians(pitch)

        # --------------------------- FORWARD VECTOR
        # calculate the camera forward direction from yaw and pitch
        cx = np.cos(pitch_rad) * np.cos(yaw_rad)
        cy = np.cos(pitch_rad) * np.sin(yaw_rad)
        cz = np.sin(pitch_rad)
        F = np.array([cx, cy, cz])

        # --------------------------- RIGHT VECTOR
        # use a stable right vector when looking directly upward or downward
        if abs(abs(pitch) - 90) < 1e-5:
            R = np.array([0, 1, 0]) if pitch == 90 else np.array([0, -1, 0])
        else:
            R = np.array([-np.sin(yaw_rad), np.cos(yaw_rad), 0])

        # --------------------------- UP VECTOR
        # calculate the camera up direction from the right and forward vectors
        U = np.cross(R, F)

        # --------------------------- FRAME CORNERS
        # position the image plane along the camera forward direction
        Center = F * frame_distance

        # calculate the four corners of the image plane
        tl = Center - (half_size * R) + (half_size * U)
        tr = Center + (half_size * R) + (half_size * U)
        br = Center + (half_size * R) - (half_size * U)
        bl = Center - (half_size * R) - (half_size * U)

        # create a unique name containing the view index and orientation
        frame_name = f"v{i:02d} (Y:{yaw} P:{pitch})"

        # --------------------------- ASSIGN VIEW COLOUR
        # horizontal views are displayed in green
        color = 'limegreen'

        # assign different colours to upward, downward and vertical views
        if pitch == 45: color = 'dodgerblue'
        elif pitch == -45: color = 'tomato'
        elif abs(pitch) == 90: color = 'mediumorchid'

        # --------------------------- DRAW FRAME BORDER
        # connect all four image plane corners to create the frame outline
        fig.add_trace(go.Scatter3d(
            x=[tl[0], tr[0], br[0], bl[0], tl[0]],
            y=[tl[1], tr[1], br[1], bl[1], tl[1]],
            z=[tl[2], tr[2], br[2], bl[2], tl[2]],
            mode='lines', line=dict(color=color, width=3), name=frame_name, legendgroup=frame_name
        ))

        # --------------------------- FILL FRAME PLANE
        # create two triangles to fill the rectangular image plane
        fig.add_trace(go.Mesh3d(
            x=[tl[0], tr[0], br[0], bl[0]],
            y=[tl[1], tr[1], br[1], bl[1]],
            z=[tl[2], tr[2], br[2], bl[2]],
            i=[0, 0], j=[1, 2], k=[2, 3],
            color=color, opacity=0.2, showlegend=False, hoverinfo='skip', legendgroup=frame_name
        ))

    # --------------------------- CONFIGURE LAYOUT
    # set the title, scene dimensions, axis ranges and legend position
    fig.update_layout(
        title=dict(
            text=(
                "Camera View Simulator"
                f"<br><sup>Coverage: {HORIZONTAL_COVERAGE} "
                f"({HORIZONTAL_COVERAGE_DEGREES}°) | "
                f"Total Views: {len(views)} | FOV: {FIELD_OF_VIEW}°</sup>"
            ),
            x=0.5,
        ),
        width=800, height=800,
        scene=dict(
            xaxis=dict(range=[-axis_range, axis_range], visible=False),
            yaxis=dict(range=[-axis_range, axis_range], visible=False),
            zaxis=dict(range=[-axis_range, axis_range], visible=False),
            aspectmode='cube'
        ),
        margin=dict(l=0, r=0, b=0, t=60),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, itemsizing='constant', font=dict(size=10))
    )

    # --------------------------- RETURN FIGURE
    return fig
