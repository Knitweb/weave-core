"""Signed observation records ("findings").

A finding is one recognized object at one moment in the physical world.
Its body is serialized as canonical JSON (sorted keys, no whitespace),
its id is the SHA-256 of those canonical bytes, and it is signed with
the observer's Ed25519 key. Observers are identified by a did:key —
the same self-certifying identity pattern used across the Knitweb P2P
stack (gither), so no registration server is ever required.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from nacl.encoding import RawEncoder
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

# -- base58btc + did:key (multicodec ed25519-pub) --------------------------

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58_ALPHABET[r] + out
    pad = len(data) - len(data.lstrip(b"\0"))
    return "1" * pad + out


def _b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + _B58_ALPHABET.index(ch)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    pad = len(s) - len(s.lstrip("1"))
    return b"\0" * pad + body


def did_from_verify_key(vk: VerifyKey) -> str:
    """did:key with the 0xED 0x01 ed25519-pub multicodec prefix."""
    return "did:key:z" + _b58encode(b"\xed\x01" + vk.encode(RawEncoder))


def verify_key_from_did(did: str) -> VerifyKey:
    if not did.startswith("did:key:z"):
        raise ValueError(f"unsupported did: {did}")
    raw = _b58decode(did[len("did:key:z"):])
    if raw[:2] != b"\xed\x01":
        raise ValueError("did:key is not ed25519-pub")
    return VerifyKey(raw[2:])


# -- canonical serialization ----------------------------------------------

def canonical_bytes(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class Finding:
    """One recognized object, positioned in the world."""

    label: str                      # e.g. "bicycle" (COCO class name)
    confidence: float               # detector confidence in [0, 1]
    geopose: dict                   # OGC GeoPose Basic-YPR dict of the OBJECT
    observer_pose: dict             # GeoPose of the CAMERA at capture time
    bbox: list                      # [x1, y1, x2, y2] pixels in source frame
    image_sha256: str               # hash of the source frame (frame itself stays local)
    source: str = "server-yolo"     # "server-yolo" | "client-webgpu" | "unity-sentis"
    observed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def body(self) -> dict:
        return {
            "kind": "geoweave.finding", "v": 1,
            "label": self.label,
            "confidence": round(float(self.confidence), 4),
            "geopose": self.geopose,
            "observer_pose": self.observer_pose,
            "bbox": [round(float(v), 1) for v in self.bbox],
            "image_sha256": self.image_sha256,
            "source": self.source,
            "observed_at": self.observed_at,
        }

    @property
    def id(self) -> str:
        return hashlib.sha256(canonical_bytes(self.body())).hexdigest()


# -- signing / verification ------------------------------------------------

def sign_finding(finding: Finding, key: SigningKey) -> dict:
    """Wrap a finding in a signed gossip envelope (the P2P wire format)."""
    body = finding.body()
    sig = key.sign(canonical_bytes(body)).signature
    return {
        "type": "geoweave.finding.announce", "v": 1,
        "id": finding.id,
        "body": body,
        "did": did_from_verify_key(key.verify_key),
        "sig": sig.hex(),
    }


def verify_envelope(env: dict) -> bool:
    """True iff the envelope's signature and id both check out."""
    try:
        body = env["body"]
        digest = hashlib.sha256(canonical_bytes(body)).hexdigest()
        if digest != env["id"]:
            return False
        vk = verify_key_from_did(env["did"])
        vk.verify(canonical_bytes(body), bytes.fromhex(env["sig"]))
        return True
    except (KeyError, ValueError, BadSignatureError):
        return False
