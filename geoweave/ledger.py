"""Append-only finding ledger with P2P gossip merge.

Storage is a single SQLite file: content-addressed rows (the finding id
is the SHA-256 of its canonical body), each carrying its signature and
signer did. `merge()` ingests envelopes received from peers — every row
is re-verified locally, so a malicious peer cannot inject or mutate
findings. Export is standard GeoJSON so any GIS tool can read the map.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .finding import verify_envelope

_SCHEMA = """
CREATE TABLE IF NOT EXISTS findings (
    id          TEXT PRIMARY KEY,
    body        TEXT NOT NULL,      -- canonical JSON body
    sig         TEXT NOT NULL,      -- Ed25519 signature, hex
    did         TEXT NOT NULL,      -- signer did:key
    label       TEXT NOT NULL,
    lat         REAL NOT NULL,
    lon         REAL NOT NULL,
    observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_label ON findings(label);
CREATE INDEX IF NOT EXISTS idx_findings_time  ON findings(observed_at);
"""


class FindingLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.executescript(_SCHEMA)

    # -- writes ------------------------------------------------------------
    def add(self, envelope: dict) -> bool:
        """Verify + insert one signed envelope. Returns True if stored."""
        if not verify_envelope(envelope):
            return False
        body = envelope["body"]
        pos = body["geopose"]["position"]
        try:
            self.db.execute(
                "INSERT INTO findings VALUES (?,?,?,?,?,?,?,?)",
                (
                    envelope["id"], json.dumps(body, sort_keys=True),
                    envelope["sig"], envelope["did"], body["label"],
                    pos["lat"], pos["lon"], body["observed_at"],
                ),
            )
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # duplicate id: already known, not an error for gossip

    def merge(self, envelopes: Iterable[dict]) -> dict:
        """Gossip ingest: verify-and-union a batch from a peer."""
        stats = {"accepted": 0, "duplicate_or_invalid": 0}
        for env in envelopes:
            if self.add(env):
                stats["accepted"] += 1
            else:
                stats["duplicate_or_invalid"] += 1
        return stats

    # -- reads -------------------------------------------------------------
    def get(self, finding_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT body, sig, did FROM findings WHERE id=?", (finding_id,)
        ).fetchone()
        if row is None:
            return None
        return {"id": finding_id, "body": json.loads(row[0]), "sig": row[1], "did": row[2]}

    def all_envelopes(self, limit: int = 10_000) -> list[dict]:
        rows = self.db.execute(
            "SELECT id, body, sig, did FROM findings ORDER BY observed_at LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"type": "geoweave.finding.announce", "v": 1,
             "id": r[0], "body": json.loads(r[1]), "sig": r[2], "did": r[3]}
            for r in rows
        ]

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM findings").fetchone()[0]

    # -- export ------------------------------------------------------------
    def to_geojson(self, limit: int = 10_000) -> dict:
        feats = []
        for env in self.all_envelopes(limit):
            b = env["body"]
            pos = b["geopose"]["position"]
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point",
                             "coordinates": [pos["lon"], pos["lat"], pos.get("h", 0.0)]},
                "properties": {
                    "id": env["id"], "label": b["label"],
                    "confidence": b["confidence"], "observed_at": b["observed_at"],
                    "source": b["source"], "did": env["did"],
                },
            })
        return {"type": "FeatureCollection", "features": feats}
