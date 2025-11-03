import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPO_DIR = ROOT / "topologie"

count = 0
updated = []
for path in sorted(TOPO_DIR.rglob('*.json')):
    try:
        txt = path.read_text(encoding='utf-8')
        raw = json.loads(txt)
    except Exception as exc:
        print(f"SKIP (invalid json): {path}: {exc}")
        continue
    geometry = raw.get('geometry')
    if not isinstance(geometry, dict):
        print(f"SKIP (no geometry): {path}")
        continue
    changed = False
    # Set/overwrite defaults
    if geometry.get('N') != 500:
        geometry['N'] = 500
        changed = True
    if geometry.get('lat') != 500:
        geometry['lat'] = 500
        changed = True
    if geometry.get('lon') != 16:
        geometry['lon'] = 16
        changed = True
    if changed:
        raw['geometry'] = geometry
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
        count += 1
        updated.append(str(path.relative_to(ROOT)))

print(f"Updated {count} files")
for p in updated:
    print(p)
