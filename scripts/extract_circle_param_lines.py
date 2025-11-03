import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPO_DIR = ROOT / "topologie"

keywords = ['N', 'lat', 'lon', 'anneau', 'colonne', 'rings', 'ring', 'cols', 'columns']

matches = []
for path in sorted(TOPO_DIR.rglob('*.json')):
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        continue
    code = raw.get('geometry', {}).get('code') or raw.get('code')
    if not code:
        continue
    lines = code.splitlines()
    for i, line in enumerate(lines, start=1):
        low = line.lower()
        for kw in keywords:
            if kw.lower() in low:
                start = max(0, i-3)
                end = min(len(lines), i+2)
                context = '\n'.join(f"{ln:4}: {lines[ln-1]}" for ln in range(start+1, end+1))
                matches.append((str(path.relative_to(ROOT)), i, kw, context))
                break

# Print summary
by_file = {}
for f, i, kw, ctx in matches:
    by_file.setdefault(f, []).append((i, kw, ctx))

print(f"Found matches in {len(by_file)} files\n")
for f, items in sorted(by_file.items()):
    print(f"== {f}")
    for i, kw, ctx in items:
        print(f"--- match at line {i} (keyword: {kw}) ---")
        print(ctx)
    print()
