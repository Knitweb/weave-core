"""Pulse contract: the committed fixture must match our canonical form exactly.

`Knitweb/pulse` verifies the same fixture bytes with `knitweb.geoweave.bridge`
in its own suite. If GeoWeave ever changes canonical serialization, signing,
or the envelope shape, this test goes red here — and the mirror test goes red
there — instead of the two repos drifting apart silently.
"""

import json
import sys
from pathlib import Path

from geoweave.finding import verify_envelope

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from make_pulse_contract_fixture import FIXTURE, build_envelope  # noqa: E402


def test_fixture_matches_regenerated_envelope_byte_for_byte():
    committed = json.loads(FIXTURE.read_text())
    assert committed == build_envelope(), (
        "canonical form changed — regenerate the fixture ONLY if the change is "
        "intentional, and update the mirror test in Knitweb/pulse in the same "
        "release"
    )


def test_fixture_verifies():
    committed = json.loads(FIXTURE.read_text())
    assert verify_envelope(committed)
    # and stays refused when tampered
    tampered = {**committed, "body": {**committed["body"], "label": "gold_bar"}}
    assert not verify_envelope(tampered)
