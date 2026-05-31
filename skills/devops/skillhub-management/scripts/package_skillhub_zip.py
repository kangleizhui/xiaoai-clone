#!/usr/bin/env python3
"""Package a SkillHub skill directory for web upload.

Usage:
  python scripts/package_skillhub_zip.py /path/to/skill-dir /tmp/my-skill.zip

The output zip has SKILL.md at the archive root and optionally includes
references/, templates/, scripts/, and assets/ subdirectories. It refuses
archives over 10 MiB because SkillHub's web uploader rejects larger files.
"""
from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024
ALLOWED_DIRS = ("references", "templates", "scripts", "assets")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    src = Path(sys.argv[1]).expanduser().resolve()
    out = Path(sys.argv[2]).expanduser().resolve()
    skill_md = src / "SKILL.md"
    if not skill_md.is_file():
        print(f"ERROR: {src} does not contain SKILL.md", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    files: list[tuple[Path, str]] = [(skill_md, "SKILL.md")]
    for dirname in ALLOWED_DIRS:
        d = src / dirname
        if d.is_dir():
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    files.append((p, str(p.relative_to(src))))

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, arcname in files:
            zf.write(path, arcname)

    size = out.stat().st_size
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "SKILL.md" in names

    print(f"Wrote {out} ({size} bytes, {len(files)} files)")
    if size > MAX_BYTES:
        print(f"ERROR: archive exceeds 10 MiB SkillHub limit: {size}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
