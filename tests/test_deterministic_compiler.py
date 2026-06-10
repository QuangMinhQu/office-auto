"""test_deterministic_compiler.py — golden tests for the deterministic pipeline (v3).

Tests source_packet_to_ops.py, validate_ops_strict.py, and final_gate.py.
Uses fixtures created programmatically (no large DOCX template needed for compiler tests).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / ".opencode/skills/md-to-docx-pipeline/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import source_packet_to_ops as compiler
import validate_ops_strict as strict_validator
import source_packet as sp


class SourcePacketToOpsTests(unittest.TestCase):
    """Test the deterministic compiler."""

    def test_compiles_simple_markdown(self) -> None:
        """Simple markdown → correct number of insert + remove ops."""
        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 6,
            "block_count": 5,
            "blocks": [
                {"id": "B0001", "type": "heading", "text": "# CHAPTER 1", "line_start": 1, "line_end": 2},
                {"id": "B0002", "type": "paragraph", "text": "Some body text.", "line_start": 3, "line_end": 4},
                {"id": "B0003", "type": "heading", "text": "## Section 1.1", "line_start": 5, "line_end": 6},
                {"id": "B0004", "type": "paragraph", "text": "More text here.", "line_start": 7, "line_end": 8},
                {"id": "B0005", "type": "paragraph", "text": "Final paragraph.", "line_start": 9, "line_end": 10},
            ],
        }
        style_map = {
            "h1": "Heading1",
            "h2": "Heading2",
            "h3": "Heading3",
            "body": "Normal",
            "caption": "Caption",
        }
        replace_range = {
            "insert_after_path": "/body/p[@paraId=49349C0D]",
            "remove_paths": [
                "/body/p[@paraId=PLACEHOLDER1]",
                "/body/p[@paraId=PLACEHOLDER2]",
            ],
        }

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)

        self.assertEqual(result["version"], "2")
        self.assertIn("ops", result)
        ops = result["ops"]
        insert_ops = [op for op in ops if op["op"] != "remove"]
        remove_ops = [op for op in ops if op["op"] == "remove"]

        self.assertEqual(len(insert_ops), 5)
        self.assertEqual(len(remove_ops), 2)

    def test_first_insert_has_explicit_anchor(self) -> None:
        """First insert op MUST have explicit anchor, not PREVIOUS."""
        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 2,
            "block_count": 1,
            "blocks": [
                {"id": "B0001", "type": "heading", "text": "# Title", "line_start": 1, "line_end": 2},
            ],
        }
        style_map = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "body": "Normal"}
        replace_range = {"insert_after_path": "/body/p[@paraId=ABCD]", "remove_paths": []}

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)
        insert_ops = [op for op in result["ops"] if op["op"] != "remove"]

        self.assertGreater(len(insert_ops), 0)
        first_anchor = insert_ops[0]["anchor"]
        self.assertNotEqual(first_anchor.upper(), "PREVIOUS")
        self.assertEqual(first_anchor, "/body/p[@paraId=ABCD]")

    def test_subsequent_inserts_use_previous(self) -> None:
        """Second and later insert ops must use PREVIOUS."""
        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 3,
            "block_count": 3,
            "blocks": [
                {"id": "B0001", "type": "heading", "text": "# Title", "line_start": 1, "line_end": 2},
                {"id": "B0002", "type": "paragraph", "text": "Body 1", "line_start": 3, "line_end": 4},
                {"id": "B0003", "type": "paragraph", "text": "Body 2", "line_start": 5, "line_end": 6},
            ],
        }
        style_map = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "body": "Normal"}
        replace_range = {"insert_after_path": "/body/p[@paraId=ABCD]", "remove_paths": []}

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)
        insert_ops = [op for op in result["ops"] if op["op"] != "remove"]

        self.assertEqual(len(insert_ops), 3)
        self.assertNotEqual(insert_ops[0]["anchor"].upper(), "PREVIOUS")
        self.assertEqual(insert_ops[1]["anchor"].upper(), "PREVIOUS")
        self.assertEqual(insert_ops[2]["anchor"].upper(), "PREVIOUS")

    def test_strips_heading_markers(self) -> None:
        """Heading text must have # stripped."""
        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 2,
            "block_count": 1,
            "blocks": [
                {"id": "B0001", "type": "heading", "text": "## This is a Section", "line_start": 1, "line_end": 2},
            ],
        }
        style_map = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "body": "Normal"}
        replace_range = {"insert_after_path": "/body/p[@paraId=ABCD]", "remove_paths": []}

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)
        insert_ops = [op for op in result["ops"] if op["op"] != "remove"]

        self.assertEqual(len(insert_ops), 1)
        self.assertNotIn("##", insert_ops[0]["text"])
        self.assertEqual(insert_ops[0]["text"], "This is a Section")

    def test_copies_text_verbatim(self) -> None:
        """Text must be copied verbatim, never paraphrased."""
        original = "Thị giác máy tính (Computer Vision) là lĩnh vực nghiên cứu nhằm..."
        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 2,
            "block_count": 1,
            "blocks": [
                {"id": "B0001", "type": "paragraph", "text": original, "line_start": 1, "line_end": 2},
            ],
        }
        style_map = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "body": "Normal"}
        replace_range = {"insert_after_path": "/body/p[@paraId=ABCD]", "remove_paths": []}

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)
        insert_ops = [op for op in result["ops"] if op["op"] != "remove"]

        self.assertEqual(len(insert_ops), 1)
        self.assertEqual(insert_ops[0]["text"], original)

    def test_every_insert_has_source_block_id_and_hash(self) -> None:
        """Every insert op must have source_block_id and source_text_sha256."""
        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 3,
            "block_count": 2,
            "blocks": [
                {"id": "B0001", "type": "heading", "text": "# Title", "line_start": 1, "line_end": 2},
                {"id": "B0002", "type": "paragraph", "text": "Body text.", "line_start": 3, "line_end": 4},
            ],
        }
        style_map = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "body": "Normal"}
        replace_range = {"insert_after_path": "/body/p[@paraId=ABCD]", "remove_paths": []}

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)
        insert_ops = [op for op in result["ops"] if op["op"] != "remove"]

        for i, op in enumerate(insert_ops):
            self.assertIn("source_block_id", op, f"Op {i} missing source_block_id")
            self.assertIn("source_text_sha256", op, f"Op {i} missing source_text_sha256")
            self.assertEqual(len(op["source_text_sha256"]), 64)

    def test_empty_lines_become_empty_paragraphs(self) -> None:
        """Empty line blocks become insert ops with empty text."""
        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 3,
            "block_count": 2,
            "blocks": [
                {"id": "B0001", "type": "paragraph", "text": "Before", "line_start": 1, "line_end": 2},
                {"id": "B0002", "type": "empty_line", "text": "", "line_start": 3, "line_end": 4},
            ],
        }
        style_map = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "body": "Normal"}
        replace_range = {"insert_after_path": "/body/p[@paraId=ABCD]", "remove_paths": []}

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)
        insert_ops = [op for op in result["ops"] if op["op"] != "remove"]

        self.assertEqual(len(insert_ops), 2)
        self.assertEqual(insert_ops[1]["text"], "")

    def test_remove_ops_appended_after_inserts(self) -> None:
        """All remove ops must be after all insert ops."""
        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 2,
            "block_count": 1,
            "blocks": [
                {"id": "B0001", "type": "heading", "text": "# Title", "line_start": 1, "line_end": 2},
            ],
        }
        style_map = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "body": "Normal"}
        replace_range = {
            "insert_after_path": "/body/p[@paraId=ABCD]",
            "remove_paths": ["/body/p[@paraId=X]", "/body/p[@paraId=Y]"],
        }

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)
        ops = result["ops"]

        last_insert_idx = max(
            i for i, op in enumerate(ops) if op["op"] not in ("remove",)
        )
        first_remove_idx = min(
            i for i, op in enumerate(ops) if op["op"] == "remove"
        )

        self.assertLess(last_insert_idx, first_remove_idx)

    def test_caption_candidate_uses_caption_style(self) -> None:
        """Caption candidate blocks use the caption style from style_map."""
        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 2,
            "block_count": 1,
            "blocks": [
                {"id": "B0001", "type": "caption_candidate", "text": "[Hình 1.1: Mô tả]", "line_start": 1, "line_end": 2},
            ],
        }
        style_map = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "body": "Normal", "caption": "Caption"}
        replace_range = {"insert_after_path": "/body/p[@paraId=ABCD]", "remove_paths": []}

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)
        insert_ops = [op for op in result["ops"] if op["op"] != "remove"]

        self.assertEqual(len(insert_ops), 1)
        self.assertEqual(insert_ops[0]["style"], "Caption")

    def test_handles_125_blocks_without_truncation(self) -> None:
        """Compiler handles 125 blocks — no truncation, no chunking needed."""
        blocks = []
        for i in range(125):
            if i % 4 == 0:
                blocks.append({"id": f"B{i+1:04d}", "type": "heading", "text": f"# Section {i}", "line_start": i+1, "line_end": i+2})
            elif i % 4 == 1:
                blocks.append({"id": f"B{i+1:04d}", "type": "paragraph", "text": f"Body text block {i}.", "line_start": i+1, "line_end": i+2})
            elif i % 4 == 2:
                blocks.append({"id": f"B{i+1:04d}", "type": "paragraph", "text": f"More text {i}.", "line_start": i+1, "line_end": i+2})
            else:
                blocks.append({"id": f"B{i+1:04d}", "type": "empty_line", "text": "", "line_start": i+1, "line_end": i+2})

        source_packet = {
            "source_file": "/tmp/test.md",
            "sha256": "abc123",
            "line_count": 125,
            "block_count": 125,
            "blocks": blocks,
        }
        style_map = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "body": "Normal"}
        replace_range = {"insert_after_path": "/body/p[@paraId=ABCD]", "remove_paths": [f"/body/p[@paraId=P{i}]" for i in range(57)]}

        result = compiler.compile_source_packet_to_ops(source_packet, style_map, replace_range)
        insert_ops = [op for op in result["ops"] if op["op"] != "remove"]
        remove_ops = [op for op in result["ops"] if op["op"] == "remove"]

        self.assertEqual(len(insert_ops), 125, "All 125 blocks must produce insert ops")
        self.assertEqual(len(remove_ops), 57, "All 57 placeholder paths must produce remove ops")
        self.assertEqual(len(result["ops"]), 182, "Total ops = insert + remove")


class StrictValidatorTests(unittest.TestCase):
    """Test hard-block validation logic."""

    def _make_inspection(self) -> dict:
        return {
            "styles_raw": [{"style_id": "Normal"}, {"style_id": "Heading1"}, {"style_id": "Heading2"}],
            "all_para_ids": [
                {"para_id": "ABCD", "text_preview": "Front matter", "is_front_matter": True},
                {"para_id": "PLACE1", "text_preview": "Body placeholder 1", "is_front_matter": False},
                {"para_id": "PLACE2", "text_preview": "Body placeholder 2", "is_front_matter": False},
            ],
            "paragraph_sample": [{"para_id": "ABCD"}, {"para_id": "PLACE1"}],
            "body_children": [{"path": "/body/p[@paraId=ABCD]"}, {"path": "/body/p[@paraId=PLACE1]"}],
            "body_paragraphs": [{"path": "/body/p[@paraId=ABCD]"}, {"path": "/body/p[@paraId=PLACE1]"}],
        }

    def test_valid_ops_pass(self) -> None:
        """Well-formed ops should pass strict validation."""
        ops = [
            {"op": "insert_paragraph_after", "role": "h1", "anchor": "/body/p[@paraId=ABCD]", "style": "Heading1", "text": "Title", "source_block_id": "B0001"},
            {"op": "insert_paragraph_after", "role": "body", "anchor": "PREVIOUS", "style": "Normal", "text": "Body", "source_block_id": "B0002"},
            {"op": "remove", "path": "/body/p[@paraId=PLACE1]"},
        ]

        blocking = strict_validator.strict_invariant_checks(ops, self._make_inspection())
        self.assertEqual(len(blocking), 0, f"Expected no blocking errors, got: {blocking}")

    def test_first_insert_previously_blocks(self) -> None:
        """First op using PREVIOUS should be blocked."""
        ops = [
            {"op": "insert_paragraph_after", "role": "h1", "anchor": "PREVIOUS", "style": "Heading1", "text": "Title"},
        ]

        blocking = strict_validator.strict_invariant_checks(ops, self._make_inspection())
        first_anchor_errors = [e for e in blocking if "first_insert" in e.get("invariant", "")]
        self.assertGreater(len(first_anchor_errors), 0)

    def test_non_previous_mid_sequence_blocks(self) -> None:
        """Mid-sequence insert not using PREVIOUS should be blocked."""
        ops = [
            {"op": "insert_paragraph_after", "role": "h1", "anchor": "/body/p[@paraId=ABCD]", "style": "Heading1", "text": "Title", "source_block_id": "B0001"},
            {"op": "insert_paragraph_after", "role": "body", "anchor": "/body/p[@paraId=ANOTHER]", "style": "Normal", "text": "Body", "source_block_id": "B0002"},
        ]

        blocking = strict_validator.strict_invariant_checks(ops, self._make_inspection())
        non_prev_errors = [e for e in blocking if "non_previous" in e.get("invariant", "")]
        self.assertGreater(len(non_prev_errors), 0)

    def test_remove_front_matter_blocks(self) -> None:
        """Remove op targeting front matter should be blocked."""
        ops = [
            {"op": "insert_paragraph_after", "role": "h1", "anchor": "/body/p[@paraId=ABCD]", "style": "Heading1", "text": "Title", "source_block_id": "B0001"},
            {"op": "remove", "path": "/body/p[@paraId=ABCD]"},
        ]

        inspection = self._make_inspection()
        blocking = strict_validator.strict_invariant_checks(ops, inspection)
        fm_errors = [e for e in blocking if "remove_front_matter" in e.get("invariant", "")]
        self.assertGreater(len(fm_errors), 0)

    def test_unsupported_op_blocks(self) -> None:
        """Unsupported op type should be blocked."""
        ops = [
            {"op": "insert_paragraph_after", "role": "h1", "anchor": "/body/p[@paraId=ABCD]", "style": "Heading1", "text": "Title", "source_block_id": "B0001"},
            {"op": "delete_paragraph", "path": "/body/p[@paraId=PLACE1]"},
        ]

        blocking = strict_validator.strict_invariant_checks(ops, self._make_inspection())
        unsupported = [e for e in blocking if "unsupported" in e.get("invariant", "")]
        self.assertGreater(len(unsupported), 0)

    def test_remove_at_not_path_blocks(self) -> None:
        """Remove op using 'at' instead of 'path' should be blocked."""
        ops = [
            {"op": "insert_paragraph_after", "role": "h1", "anchor": "/body/p[@paraId=ABCD]", "style": "Heading1", "text": "Title", "source_block_id": "B0001"},
            {"op": "remove", "at": "/body/p[@paraId=PLACE1]"},
        ]

        blocking = strict_validator.strict_invariant_checks(ops, self._make_inspection())
        at_errors = [e for e in blocking if "remove_uses_at" in e.get("invariant", "")]
        self.assertGreater(len(at_errors), 0)

    def test_duplicate_source_block_id_blocks(self) -> None:
        """Duplicate source_block_id should be blocked."""
        ops = [
            {"op": "insert_paragraph_after", "role": "h1", "anchor": "/body/p[@paraId=ABCD]", "style": "Heading1", "text": "Title", "source_block_id": "B0001"},
            {"op": "insert_paragraph_after", "role": "body", "anchor": "PREVIOUS", "style": "Normal", "text": "Body1", "source_block_id": "B0001"},
        ]

        blocking = strict_validator.strict_invariant_checks(ops, self._make_inspection())
        dup_errors = [e for e in blocking if "duplicate" in e.get("invariant", "")]
        self.assertGreater(len(dup_errors), 0)


class SourcePacketTests(unittest.TestCase):
    """Test the mechanical markdown parser."""

    def test_classifies_heading(self) -> None:
        self.assertEqual(sp.classify_line("# Chapter 1"), "heading")
        self.assertEqual(sp.classify_line("## Section 1.1"), "heading")
        self.assertEqual(sp.classify_line("### Sub"), "heading")

    def test_classifies_caption(self) -> None:
        self.assertEqual(sp.classify_line("[Hình 1.1: Mô tả]"), "caption_candidate")
        self.assertEqual(sp.classify_line("[Bảng 2: Dữ liệu]"), "caption_candidate")

    def test_classifies_list(self) -> None:
        self.assertEqual(sp.classify_line("- Item 1"), "list_item")
        self.assertEqual(sp.classify_line("1. First"), "list_item")

    def test_classifies_empty(self) -> None:
        self.assertEqual(sp.classify_line(""), "empty_line")
        self.assertEqual(sp.classify_line("   "), "empty_line")

    def test_classifies_paragraph(self) -> None:
        self.assertEqual(sp.classify_line("Plain text."), "paragraph")

    def test_splits_into_blocks(self) -> None:
        lines = [
            "# Title",
            "",
            "Body text.",
            "[Hình 1: Test]",
        ]
        blocks = sp.split_into_blocks(lines)

        self.assertEqual(len(blocks), 4)
        self.assertEqual(blocks[0]["type"], "heading")
        self.assertEqual(blocks[1]["type"], "empty_line")
        self.assertEqual(blocks[2]["type"], "paragraph")
        self.assertEqual(blocks[3]["type"], "caption_candidate")

    def test_hashes_are_stable(self) -> None:
        h1 = compiler.compute_text_sha256("test")
        h2 = compiler.compute_text_sha256("test")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)


if __name__ == "__main__":
    unittest.main()
