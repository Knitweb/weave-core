"""GeoWeave — P2P geospatial capture + AR object recognition.

Modules:
  geopose  - OGC GeoPose 1.0 (Basic-YPR) data model + displacement math
  finding  - signed observation records (canonical JSON, Ed25519, did:key)
  ledger   - append-only finding ledger with gossip merge + GeoJSON export
  links    - browser exploration links for a recognized object
  vision   - YOLO object detection via onnxruntime (CPU)
  server   - FastAPI near-live inference + exploration endpoints
"""

__version__ = "0.1.0"
