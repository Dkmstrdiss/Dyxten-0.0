#!/usr/bin/env python3
"""Export the control UI sources as raw text and a zip archive."""
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


def find_targets(root: Path) -> list[Path]:
    control_dir = root / "core" / "control"
    targets = [p for p in control_dir.glob("*.py") if p.is_file()]
    return sorted(targets, key=lambda p: p.name)


def export_bundle(root: Path, out_dir: Path, targets: list[Path]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle_txt = out_dir / "control_ui_bundle.txt"
    with bundle_txt.open("w", encoding="utf-8") as fh:
        fh.write("# Dyxten control UI source bundle\n\n")
        for path in targets:
            rel = path.relative_to(root)
            fh.write(f"## {rel.as_posix()}\n\n")
            text = path.read_text(encoding="utf-8")
            fh.write(text)
            if not text.endswith("\n"):
                fh.write("\n")
            fh.write("\n")

    bundle_zip = out_dir / "control_ui_bundle.zip"
    with zipfile.ZipFile(bundle_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in targets:
            rel = path.relative_to(root)
            zf.write(path, arcname=rel.as_posix())

    return bundle_txt, bundle_zip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root containing the control sources.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "artifacts",
        help="Directory where the bundle files will be written.",
    )
    args = parser.parse_args()

    targets = find_targets(args.root)
    if not targets:
        raise SystemExit("no control sources found")

    txt_path, zip_path = export_bundle(args.root, args.out, targets)
    print(f"wrote {txt_path.relative_to(args.root)}")
    print(f"wrote {zip_path.relative_to(args.root)}")


if __name__ == "__main__":
    main()
