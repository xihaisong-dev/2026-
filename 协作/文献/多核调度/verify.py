"""Verify the unmodified downloaded literature against its manifest."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
records = json.loads((root / "文献清单.json").read_text(encoding="utf-8"))["records"]
assert len(records) == 5, "Expected five papers"
for record in records:
    path = root / record["file"]
    data = path.read_bytes()
    assert data.startswith(b"%PDF-"), path
    assert len(data) == record["bytes"], path
    assert hashlib.sha256(data).hexdigest() == record["sha256"], path
    print(f"PASS {record['id']}: {record['pages']} pages, {len(data)} bytes")
print("PASS: all five original PDFs match their manifests")
