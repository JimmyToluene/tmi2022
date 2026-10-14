"""Shared camera conventions for the scene spec, the Blender builder and the projection checks.

World: Blender Z-up, metres. Origin = centre of the stage disc at pit-floor level (z = 0).
+Y points from DS's VIP balcony toward the far side of the club; the balcony is at negative Y.

A camera is {location, target, roll_deg, lens_mm}; sensor_fit is VERTICAL with a 36 mm sensor height,
so for the 1080x1920 portrait frame the vertical field of view is 2*atan(18/lens_mm).
roll_deg > 0 rotates the image content clockwise as seen on screen (camera rolled counter-clockwise),
matching the sign of the measured frame-to-frame rot_deg (positive = content rotates clockwise in image
coordinates with y down).
"""
import math

import numpy as np

W, H = 1080, 1920
SENSOR_H = 36.0


def look_at(location, target, roll_deg=0.0):
    """3x3 world-from-camera rotation (columns = camera X right, Y up, Z back) for a Blender camera."""
    loc, tgt = np.asarray(location, float), np.asarray(target, float)
    fwd = tgt - loc
    fwd /= np.linalg.norm(fwd)
    world_up = np.array([0.0, 0.0, 1.0])
    if abs(fwd @ world_up) > 0.999:
        world_up = np.array([0.0, 1.0, 0.0])
    right = np.cross(fwd, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    # roll about the viewing axis; positive roll = image content turns clockwise on screen
    r = math.radians(roll_deg)
    right, up = right * math.cos(r) + up * math.sin(r), up * math.cos(r) - right * math.sin(r)
    back = -fwd
    return np.stack([right, up, back], axis=1)


def project(points, location, target, roll_deg, lens_mm):
    """World points (N,3) -> pixel coords (N,2) in the 1080x1920 frame (x right, y down) and depth (N,)."""
    R = look_at(location, target, roll_deg)
    P = (np.atleast_2d(np.asarray(points, float)) - np.asarray(location, float)) @ R  # camera coords
    depth = -P[:, 2]
    f_px = lens_mm / SENSOR_H * H
    u = W / 2 + f_px * P[:, 0] / depth
    v = H / 2 - f_px * P[:, 1] / depth
    return np.stack([u, v], axis=1), depth


def euler_xyz(location, target, roll_deg):
    """Blender rotation_euler (XYZ, radians) for the camera object."""
    R = look_at(location, target, roll_deg)
    # Blender XYZ euler: R = Rz @ Ry @ Rx
    sy = -R[2, 0]
    cy = math.sqrt(max(0.0, 1 - sy * sy))
    if cy > 1e-6:
        x = math.atan2(R[2, 1], R[2, 2])
        y = math.asin(sy)
        z = math.atan2(R[1, 0], R[0, 0])
    else:
        x = math.atan2(-R[1, 2], R[1, 1])
        y = math.asin(sy)
        z = 0.0
    return (x, y, z)


def vfov_deg(lens_mm):
    return math.degrees(2 * math.atan(SENSOR_H / 2 / lens_mm))


def lens_from_scale(lens_mm, scale):
    """Equivalent focal length after a pure zoom by `scale` (image magnification)."""
    return lens_mm * scale
