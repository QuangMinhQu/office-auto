#!/usr/bin/env python3
"""docx_refresh_fields.py — Refresh all field codes via LibreOffice headless.

Uses LibreOffice's --headless --convert-to to trigger field update.
This is the only reliable way to refresh TOC/List fields without opening Word.

Strategy:
  1. Convert DOCX → DOCX via LibreOffice (triggers UpdateFields on load+save)
  2. Fallback: mark fldChar fields as dirty via python-docx/lxml

Usage:
    python docx_refresh_fields.py --target-file <path> [--strategy auto|libreoffice|mark_dirty]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _find_libreoffice() -> str | None:
    for bin_name in ("soffice", "libreoffice"):
        found = shutil.which(bin_name)
        if found:
            return found
    return None


def refresh_via_libreoffice(docx_path: Path) -> dict:
    """Refresh fields using LibreOffice headless convert-to."""
    lo_bin = _find_libreoffice()
    if not lo_bin:
        return {"success": False, "method": "libreoffice_headless", "error": "LibreOffice not found"}

    out_dir = docx_path.parent
    cmd = [
        lo_bin, "--headless",
        "--convert-to", "docx:MS Word 2007 XML",
        "--outdir", str(out_dir),
        str(docx_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return {"success": False, "method": "libreoffice_headless", "error": "Timeout after 60s"}

    converted = out_dir / f"{docx_path.stem}.docx"
    if converted.exists() and converted != docx_path:
        backup = docx_path.with_suffix(".bak.docx")
        try:
            shutil.move(str(docx_path), str(backup))
        except OSError:
            docx_path.unlink(missing_ok=True)
        shutil.move(str(converted), str(docx_path))
        return {
            "success": True,
            "method": "libreoffice_headless",
            "output": str(docx_path),
            "backup": str(backup),
            "stderr": result.stderr[:500] if result.stderr else "",
        }

    return {
        "success": False,
        "method": "libreoffice_headless",
        "error": f"Converted file not found or identical. stderr: {result.stderr[:500] if result.stderr else 'none'}",
    }


def mark_fields_dirty(docx_path: Path) -> dict:
    """Mark all fldChar fields as dirty so Word auto-refreshes on open.

    Patches document.xml inside the ZIP to set w:dirty="true" on fldChar begin elements.
    """
    tmp_path = docx_path.with_suffix(".tmp.docx")

    with zipfile.ZipFile(docx_path, "r") as zf_in:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
            for item in zf_in.infolist():
                data = zf_in.read(item.filename)
                if item.filename == "word/document.xml":
                    tree = etree.fromstring(data)
                    dirty_count = 0
                    for fld in tree.findall(f".//{{{W}}}fldChar"):
                        fld_type = fld.get(f"{{{W}}}fldCharType")
                        if fld_type == "begin":
                            fld.set(f"{{{W}}}dirty", "true")
                            dirty_count += 1
                    data = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=True)
                zf_out.writestr(item, data)

    backup = docx_path.with_suffix(".bak.docx")
    try:
        shutil.move(str(docx_path), str(backup))
    except OSError:
        docx_path.unlink(missing_ok=True)
    shutil.move(str(tmp_path), str(docx_path))
    tmp_path.unlink(missing_ok=True)

    return {
        "success": True,
        "method": "mark_dirty",
        "note": "Fields marked dirty — will refresh when opened in Word",
        "backup": str(backup),
    }


def refresh_fields(docx_path: Path, strategy: str = "auto") -> dict:
    """Refresh fields with chosen strategy.

    strategy:
      - "auto": try libreoffice, fallback to mark_dirty
      - "libreoffice": only libreoffice, fail if unavailable
      - "mark_dirty": only mark_dirty
    """
    if not docx_path.exists():
        return {"success": False, "method": "none", "error": f"File not found: {docx_path}"}

    lo_available = _find_libreoffice() is not None

    if strategy == "auto":
        if lo_available:
            result = refresh_via_libreoffice(docx_path)
            if result["success"]:
                return result
            print(f"[docx_refresh_fields] LibreOffice failed, falling back to mark_dirty: {result.get('error')}")
        return mark_fields_dirty(docx_path)

    if strategy == "libreoffice":
        if not lo_available:
            return {"success": False, "method": "libreoffice_headless", "error": "LibreOffice not found"}
        return refresh_via_libreoffice(docx_path)

    if strategy == "mark_dirty":
        return mark_fields_dirty(docx_path)

    return {"success": False, "method": "none", "error": f"Unknown strategy: {strategy}"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="docx_refresh_fields: Refresh TOC and List fields via LibreOffice or mark-dirty."
    )
    parser.add_argument("--target-file", required=True, help="Path to target .docx file")
    parser.add_argument("--strategy", default="auto",
                        choices=["auto", "libreoffice", "mark_dirty"],
                        help="Refresh strategy (default: auto)")
    parser.add_argument("--run-dir", default=None,
                        help="Run directory for writing refresh report (optional)")
    args = parser.parse_args()

    target_path = Path(args.target_file)
    result = refresh_fields(target_path, args.strategy)

    lo_available = _find_libreoffice() is not None

    report = {
        **result,
        "libreoffice_available": lo_available,
        "toc_refresh_available": lo_available,
        "toc_refresh_strategy": "libreoffice_headless" if lo_available else "word_open_required",
    }

    if args.run_dir:
        from officecli_native import write_json
        report_path = Path(args.run_dir) / "field_refresh_report.json"
        write_json(report_path, report)
        print(f"[docx_refresh_fields] Report written to: {report_path}")

    status = "ok" if result["success"] else "failed"
    print(f"[docx_refresh_fields] {status}: {result.get('method', 'none')} — {result.get('note', result.get('error', ''))}")

    if not result["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
