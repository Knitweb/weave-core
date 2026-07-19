"""Core tests: geopose math, signed findings, ledger merge, links."""

import math

import pytest
from nacl.signing import SigningKey

from geoweave.finding import (
    Finding, did_from_verify_key, sign_finding, verify_envelope,
    verify_key_from_did,
)
from geoweave.geopose import GeoPose, project_detection
from geoweave.ledger import FindingLedger
from geoweave.links import build_links

AMS = GeoPose(lat=52.370216, lon=4.895168, h=2.0, yaw=0.0)


# -- geopose ---------------------------------------------------------------

def test_displacement_north_10m():
    p = AMS.displaced(0.0, 10.0)
    assert p.lat > AMS.lat and abs(p.lon - AMS.lon) < 1e-9
    assert AMS.distance_to(p) == pytest.approx(10.0, rel=1e-3)


def test_displacement_east_100m():
    p = AMS.displaced(90.0, 100.0)
    assert p.lon > AMS.lon
    assert AMS.distance_to(p) == pytest.approx(100.0, rel=1e-3)


def test_geopose_roundtrip_and_validation():
    assert GeoPose.from_dict(AMS.to_dict()) == AMS
    with pytest.raises(ValueError):
        GeoPose(lat=91.0, lon=0.0)


def test_project_detection_center_goes_straight_ahead():
    cam = GeoPose(lat=52.0, lon=4.0, yaw=45.0)
    obj = project_detection(cam, cx_norm=0.5, cy_norm=0.5, distance_m=8.0)
    assert cam.distance_to(obj) == pytest.approx(8.0, rel=1e-3)
    assert obj.yaw == pytest.approx(45.0)


def test_project_detection_right_edge_bears_right():
    cam = GeoPose(lat=52.0, lon=4.0, yaw=0.0)
    obj = project_detection(cam, cx_norm=1.0, cy_norm=0.5, hfov_deg=72.0)
    assert obj.yaw == pytest.approx(36.0)  # half the horizontal FOV


# -- findings + signatures -------------------------------------------------

def _finding() -> Finding:
    cam = AMS.to_dict()
    return Finding(
        label="bicycle", confidence=0.91,
        geopose=AMS.displaced(10, 5).to_dict(), observer_pose=cam,
        bbox=[10, 20, 110, 220], image_sha256="ab" * 32,
    )


def test_finding_id_is_stable_and_canonical():
    f = _finding()
    assert f.id == _finding().id and len(f.id) == 64


def test_sign_verify_roundtrip_and_tamper_detection():
    key = SigningKey.generate()
    env = sign_finding(_finding(), key)
    assert verify_envelope(env)
    bad = {**env, "body": {**env["body"], "label": "car"}}
    assert not verify_envelope(bad)


def test_did_key_roundtrip():
    key = SigningKey.generate()
    did = did_from_verify_key(key.verify_key)
    assert did.startswith("did:key:z6Mk")  # ed25519-pub multicodec prefix
    assert verify_key_from_did(did) == key.verify_key


# -- ledger ----------------------------------------------------------------

def test_ledger_add_merge_dedup_and_geojson(tmp_path):
    key = SigningKey.generate()
    ledger = FindingLedger(tmp_path / "l.sqlite")
    env = sign_finding(_finding(), key)
    assert ledger.add(env) and not ledger.add(env)  # dedup by content id

    peer = FindingLedger(tmp_path / "peer.sqlite")
    stats = peer.merge([env, {**env, "sig": "00" * 64}])  # one good, one forged
    assert stats == {"accepted": 1, "duplicate_or_invalid": 1}

    gj = peer.to_geojson()
    assert gj["type"] == "FeatureCollection" and len(gj["features"]) == 1
    assert gj["features"][0]["properties"]["label"] == "bicycle"


# -- links -----------------------------------------------------------------

def test_links_contain_position_and_label():
    links = build_links(52.37, 4.89, "traffic light")
    assert "52.37" in links["openstreetmap"]
    assert "traffic%20light" in links["wikipedia_label"]
    assert len(links) >= 8
