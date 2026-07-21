#!/usr/bin/env python3
"""Regenerate the pulse contract fixture (tests/fixtures/pulse_contract_finding.json).

The fixture is a fully deterministic signed finding envelope: fixed Ed25519
seed, fixed body, fixed timestamp. It pins GeoWeave's canonical form so that
`Knitweb/pulse` (knitweb.geoweave.bridge) can verify the exact same bytes in
its own test suite — if either repo changes its canonical serialization or
signing, one of the two suites goes red instead of drifting silently.

Run from the repo root:  python3 scripts/make_pulse_contract_fixture.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nacl.signing import SigningKey  # noqa: E402

from geoweave.finding import Finding, sign_finding  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "pulse_contract_finding.json"

# Deterministic on purpose — this is a contract, not a secret.
SEED = bytes(range(32))
OBSERVED_AT = "2026-07-20T12:00:00+00:00"


def build_envelope() -> dict:
    finding = Finding(
        label="leaching_pot",
        confidence=0.87,
        geopose={"position": {"lat": 52.370216, "lon": 4.895168, "h": 6.5},
                 "angles": {"yaw": 90.0, "pitch": 0.0, "roll": 0.0}},
        observer_pose={"position": {"lat": 52.370216, "lon": 4.895168, "h": 1.6},
                       "angles": {"yaw": 90.0, "pitch": 0.0, "roll": 0.0}},
        bbox=[100.0, 80.0, 220.0, 190.0],
        image_sha256="9c56cc51b374c3ba189210d5b6d4bf57790d351c96c47c02190ecf1e430635ab",
        source="unity-sentis",
        observed_at=OBSERVED_AT,
    )
    return sign_finding(finding, SigningKey(SEED))


if __name__ == "__main__":
    envelope = build_envelope()
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n")
    print(f"wrote {FIXTURE} (id {envelope['id'][:12]}…)")
