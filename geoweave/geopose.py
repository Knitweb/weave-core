"""OGC GeoPose 1.0 (Basic-YPR) data model + geodesic displacement.

The Basic-YPR target of OGC GeoPose 1.0 encodes a pose as a WGS84
position (lat, lon, ellipsoidal height h in meters) plus yaw/pitch/roll
angles in degrees. We keep the exact JSON shape of the standard so
findings interoperate with OSCP / Open AR Cloud tooling:

    {"position": {"lat": ..., "lon": ..., "h": ...},
     "angles":   {"yaw": ..., "pitch": ..., "roll": ...}}

Yaw is a compass-style heading in degrees (0 = north, 90 = east).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# WGS84 semi-major axis in meters; good enough for meter-scale AR offsets.
EARTH_RADIUS_M = 6_378_137.0


@dataclass(frozen=True)
class GeoPose:
    lat: float
    lon: float
    h: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0

    def __post_init__(self) -> None:
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"lat out of range: {self.lat}")
        if not (-180.0 <= self.lon <= 180.0):
            raise ValueError(f"lon out of range: {self.lon}")

    # -- OGC GeoPose Basic-YPR JSON shape ---------------------------------
    def to_dict(self) -> dict:
        return {
            "position": {"lat": self.lat, "lon": self.lon, "h": self.h},
            "angles": {"yaw": self.yaw, "pitch": self.pitch, "roll": self.roll},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GeoPose":
        pos, ang = d["position"], d.get("angles", {})
        return cls(
            lat=float(pos["lat"]), lon=float(pos["lon"]), h=float(pos.get("h", 0.0)),
            yaw=float(ang.get("yaw", 0.0)), pitch=float(ang.get("pitch", 0.0)),
            roll=float(ang.get("roll", 0.0)),
        )

    # -- displacement ------------------------------------------------------
    def displaced(self, bearing_deg: float, distance_m: float, dh: float = 0.0) -> "GeoPose":
        """Return the pose displaced `distance_m` along `bearing_deg`.

        Equirectangular approximation: exact to well under a millimeter at
        the <100 m ranges an AR headset observes, which is far below GPS /
        VPS localization error.
        """
        theta = math.radians(bearing_deg)
        dlat = (distance_m * math.cos(theta)) / EARTH_RADIUS_M
        dlon = (distance_m * math.sin(theta)) / (
            EARTH_RADIUS_M * math.cos(math.radians(self.lat))
        )
        return GeoPose(
            lat=self.lat + math.degrees(dlat),
            lon=self.lon + math.degrees(dlon),
            h=self.h + dh,
            yaw=bearing_deg, pitch=self.pitch, roll=self.roll,
        )

    def distance_to(self, other: "GeoPose") -> float:
        """Great-circle distance in meters (haversine), ignoring height."""
        p1, p2 = math.radians(self.lat), math.radians(other.lat)
        dp = p2 - p1
        dl = math.radians(other.lon - self.lon)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def project_detection(
    camera: GeoPose,
    cx_norm: float,
    cy_norm: float,
    hfov_deg: float = 72.0,
    distance_m: float = 5.0,
) -> GeoPose:
    """Project a 2D detection center to a world GeoPose.

    cx_norm / cy_norm are the bounding-box center in [0, 1] image space.
    The horizontal offset from the optical axis becomes a yaw offset
    within the camera's horizontal FOV; the vertical offset (plus camera
    pitch) tilts the ray, splitting `distance_m` into a ground-plane
    component and a height component. Without a depth map this is the
    same "assumed distance" strategy Meta's MultiObjectDetection sample
    falls back to when environment raycasts miss.
    """
    vfov_deg = hfov_deg * 3.0 / 4.0  # assume 4:3 sensor unless told otherwise
    bearing = camera.yaw + (cx_norm - 0.5) * hfov_deg
    elev = camera.pitch - (cy_norm - 0.5) * vfov_deg  # up = positive
    ground = distance_m * math.cos(math.radians(elev))
    dh = distance_m * math.sin(math.radians(elev))
    return camera.displaced(bearing, ground, dh=dh)
