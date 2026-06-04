from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / ".opencode/skills/md-to-docx-pipeline/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_report
import docx_validate_ops
import officecli_native


class ValidateOpsTests(unittest.TestCase):
    def test_validate_ops_payload_warns_for_unknown_style_and_anchor(self) -> None:
        template_inspection = {
            "styles_raw": [{"style_id": "Normal"}, {"style_id": "Heading1"}],
            "all_para_ids": [{"para_id": "001"}, {"para_id": "002"}],
            "paragraph_sample": [{"para_id": "001"}],
            "body_children": [{"path": "/body/p[1]"}],
            "body_paragraphs": [{"path": "/body/p[1]"}],
        }
        ops_payload = {
            "ops": [
                {
                    "op": "insert_paragraph_after",
                    "anchor": "/body/p[999]",
                    "style": "MissingStyle",
                    "text": "Test",
                }
            ]
        }

        warnings = docx_validate_ops.validate_ops_payload(ops_payload, template_inspection)

        self.assertEqual(len(warnings), 2)
        self.assertTrue(any(w["type"] == "unknown_anchor" for w in warnings))
        self.assertTrue(any(w["type"] == "unknown_style" for w in warnings))


class BuildReportTests(unittest.TestCase):
    def test_officecli_version_returns_text(self) -> None:
        version = build_report.officecli_version()

        self.assertIsInstance(version, str)
        self.assertTrue(version)

    def test_write_json_roundtrip(self) -> None:
        run_dir = REPO_ROOT / ".office-auto" / "state" / "test-write-json"
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            target = run_dir / "sample.json"
            build_report.write_json(target, {"a": 1})
            self.assertEqual(officecli_native.read_json(target), {"a": 1})
        finally:
            for path in sorted(run_dir.glob("*"), reverse=True):
                path.unlink(missing_ok=True)
            run_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
