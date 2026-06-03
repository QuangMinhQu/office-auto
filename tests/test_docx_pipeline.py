from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / ".opencode/skills/md-to-docx-pipeline/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import compile_execution_plan
import build_docx
import compile_execution_ops
import docx_validate_ops
import docx_inspect_raw
import document_topology_detector
import generate_markitdown_style_map
import officecli_native
import markitdown_support
import parse_markdown
import plan_mapping
import prepare_template_scaffold
import profile_template
import review_docx
import roundtrip_markitdown
import semantic_grounding


class MarkdownParserTests(unittest.TestCase):
    def test_parse_markdown_nested_inline_and_table(self) -> None:
        markdown = """# Chương 1 Tổng quan\n\nĐoạn **bold _italic_** và `code`.\n\n| Cột A | Cột B |\n| --- | --- |\n| 1 | 2 |\n"""
        blocks, outline, metadata = parse_markdown.parse_markdown_blocks(markdown)

        self.assertEqual(outline[0]["text"], "Tổng quan")
        self.assertEqual(metadata["parser"], "markdown-it-py")
        self.assertEqual(blocks[0]["type"], "heading")
        self.assertEqual(blocks[1]["type"], "paragraph")
        self.assertEqual(blocks[2]["type"], "table")
        runs = blocks[1]["runs"]
        self.assertTrue(any(run.get("bold") for run in runs))
        self.assertTrue(any(run.get("italic") for run in runs))
        self.assertTrue(any(run.get("code") for run in runs))
        self.assertEqual(blocks[2]["rows"][1]["cells"][0]["text"], "1")

    def test_parse_markdown_annotates_legal_semantic_roles(self) -> None:
        markdown = """# CHƯƠNG I QUY ĐỊNH CHUNG\n\n## Điều 1. Phạm vi điều chỉnh\n\n1. Khoản một.\n"""
        blocks, outline, _ = parse_markdown.parse_markdown_blocks(markdown)

        self.assertEqual(outline[0]["semantic_role"], "legal_chuong")
        self.assertEqual(outline[1]["semantic_role"], "legal_dieu")
        self.assertEqual(blocks[2]["semantic_role"], "legal_khoan")

    def test_parse_markdown_demotes_legal_like_heading_without_document_wide_legal_structure(self) -> None:
        markdown = """# CHƯƠNG 1 TỔNG QUAN\n\nĐây là tài liệu báo cáo thông thường.\n\n## Mục tiêu\n\nNội dung tiếp theo.\n"""
        _, outline, metadata = parse_markdown.parse_markdown_blocks(markdown)

        self.assertFalse(metadata["legal_structure_detected"])
        self.assertEqual(outline[0]["semantic_role"], "h1")
        self.assertEqual(outline[1]["semantic_role"], "h2")


class OfficeCliContractTests(unittest.TestCase):
    def test_extract_added_path_prefers_structured_path(self) -> None:
        payload = {
            "success": True,
            "data": {
                "result": {
                    "path": "/body/p[77]",
                }
            },
            "message": "Added /body/p[76]",
        }
        self.assertEqual(
            officecli_native.extract_added_path(payload, element_type="paragraph", parent="/body"),
            "/body/p[77]",
        )

    def test_extract_added_path_accepts_paraid_batch_output(self) -> None:
        payload = {
            "index": 0,
            "success": True,
            "output": "Added paragraph at /body/p[@paraId=0010259A]",
        }

        self.assertEqual(
            officecli_native.extract_added_path(payload, element_type="paragraph", parent="/body"),
            "/body/p[@paraId=0010259A]",
        )


class RawInspectTests(unittest.TestCase):
    def test_build_raw_inspection_payload_keeps_raw_samples_without_heuristics(self) -> None:
        payload = docx_inspect_raw.build_raw_inspection_payload(
            template_file=REPO_ROOT / "format_template.docx",
            officecli_version="1.0.0",
            outline_view={"headings": [{"text": "Muc luc"}]},
            stats_view={"paragraphCount": 12},
            text_view={
                "elements": [
                    {"path": "/body/p[1]", "type": "paragraph", "text": "Trang bia", "style": "Title"},
                    {"path": "/styles/style[1]", "type": "style", "text": "Normal"},
                    {"path": "/body/p[2]", "type": "paragraph", "text": "Noi dung", "style": "Normal"},
                ]
            },
            styles_tree={"path": "/styles", "type": "styles", "childCount": 4},
            numbering_tree={"path": "/numbering", "type": "numbering", "childCount": 2},
            section_results=[{"path": "/sections/sec[1]", "type": "section", "text": "sec"}],
            style_results=[{"path": "/styles/style[1]", "type": "style", "text": "Normal", "format": {"id": "Normal"}}],
            paragraph_results=[{"path": "/body/p[1]", "type": "paragraph", "text": "Trang bia", "format": {"styleId": "Title"}}],
            header_results=[{"path": "/headers/header[1]", "type": "header", "text": "Header"}],
            footer_results=[{"path": "/footers/footer[1]", "type": "footer", "text": "Footer"}],
            toc_results=[{"path": "/toc[1]", "type": "toc", "text": "Muc luc"}],
            field_results=[{"path": "/fields/field[1]", "type": "field", "text": "PAGEREF"}],
        )

        self.assertEqual(payload["counts"]["paragraphs"], 1)
        self.assertEqual(payload["styles_tree"]["path"], "/styles")
        self.assertEqual(len(payload["body_elements_sample"]), 2)
        self.assertEqual(payload["body_elements_sample"][0]["path"], "/body/p[1]")
        self.assertEqual(payload["paragraph_sample"][0]["format"]["styleId"], "Title")


class PlannerTests(unittest.TestCase):
    def test_infer_style_map_promotes_h1_when_it_matches_body(self) -> None:
        style_map = plan_mapping.infer_style_map(
            {
                "style_catalog": [
                    {"style_id": "Normal", "name": "Normal", "default": True},
                    {"style_id": "Heading2", "name": "Heading 2", "outline_level": 1, "qformat": True},
                    {"style_id": "Heading3", "name": "Heading 3", "outline_level": 2, "qformat": True},
                ],
                "style_graph": {
                    "Heading2": {"resolved_outline_level": "1"},
                    "Heading3": {"resolved_outline_level": "2"},
                },
                "prototype_catalog": {
                    "body": {"style_id": "Normal"},
                    "h1": {"style_id": "Normal"},
                    "h2": {"style_id": "Heading2"},
                    "h3": {"style_id": "Heading3"},
                },
            }
        )

        self.assertEqual(style_map["body"], "Normal")
        self.assertEqual(style_map["h1"], "Heading2")
        self.assertEqual(style_map["h2"], "Heading2")

    def test_infer_style_map_accepts_explicit_style_spec_overrides(self) -> None:
        style_map = plan_mapping.infer_style_map(
            {
                "style_catalog": [{"style_id": "Normal", "name": "Normal", "default": True}],
                "style_graph": {},
                "prototype_catalog": {"body": {"style_id": "Normal"}},
            },
            {
                "style_map": {
                    "legal_chuong": "Chuong",
                    "legal_dieu": "Dieu",
                }
            },
        )

        self.assertEqual(style_map["legal_chuong"], "Chuong")
        self.assertEqual(style_map["legal_dieu"], "Dieu")

    def test_infer_style_map_omits_legal_roles_without_signal(self) -> None:
        style_map = plan_mapping.infer_style_map(
            {
                "style_catalog": [{"style_id": "Normal", "name": "Normal", "default": True}],
                "style_graph": {},
                "prototype_catalog": {
                    "body": {"style_id": "Normal"},
                    "h1": {"style_id": "Heading1"},
                    "h2": {"style_id": "Heading2"},
                },
            }
        )

        self.assertNotIn("legal_chuong", style_map)
        self.assertNotIn("legal_dieu", style_map)

    def test_choose_replace_range_prefers_bounded_zone_when_source_has_no_references(self) -> None:
        profile = {
            "document_profile": {
                "replace_range_candidates": [
                    {"name": "after-front-matter-to-end-of-main-story", "status": "resolved", "paragraph_end_index": 100, "remove_paths": ["/body/p[2]"]},
                    {"name": "after-front-matter-before-references", "status": "resolved", "paragraph_end_index": 80, "remove_paths": ["/body/p[2]"]},
                ]
            }
        }
        outline_payload = {"outline": [{"text": "Chương I"}]}

        chosen, reason = plan_mapping.choose_replace_range(profile, outline_payload)

        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["name"], "after-front-matter-before-references")
        self.assertIn("bounded range", reason)

    def test_assess_template_guardrails_blocks_unsafe_whole_body_rewrite(self) -> None:
        guardrails = plan_mapping.assess_template_guardrails(
            {
                "header_count": 0,
                "footer_count": 0,
                "field_graph": {
                    "has_toc": False,
                    "has_list_of_figures": False,
                    "has_list_of_tables": False,
                    "pageref_anchors": [],
                },
                "prototype_catalog": {
                    "h1": {"style_id": "Normal", "style_name": "Normal"},
                    "h2": {"style_id": "Normal", "style_name": "Normal"},
                    "h3": {"style_id": "Heading3", "style_name": "Heading 3"},
                },
                "document_profile": {
                    "direct_body_child_count": 3406,
                },
            },
            {
                "remove_paths": [f"/body/p[{index}]" for index in range(1, 3393)],
            },
        )

        self.assertFalse(guardrails["build_allowed"])
        self.assertIn("whole-body-rewrite", guardrails["risk_flags"])
        self.assertIn("full-document-template-disguised-as-format", guardrails["risk_flags"])
        self.assertIn("weak-heading-prototypes", guardrails["risk_flags"])
        self.assertGreaterEqual(guardrails["selected_range_remove_ratio"], 0.99)

    def test_compile_execution_plan_uses_heading_prototype(self) -> None:
        block = {"type": "heading", "level": 1, "text": "Chương I", "runs": [{"text": "Chương I"}], "line": 1}
        operation = compile_execution_plan.compile_block_operation(
            block,
            {"h1": "Normal", "body": "Normal"},
            {"h1": {"path": "/body/p[12]"}, "body": {"path": "/body/p[13]"}},
            {},
        )

        self.assertIsNotNone(operation)
        self.assertEqual(operation["prototype_path"], "/body/p[12]")
        self.assertEqual(operation["set_props"]["text"], "Chương I")

    def test_compile_execution_plan_main_blocks_when_plan_not_ready(self) -> None:
        run_dir = REPO_ROOT / ".office-auto" / "state" / "test-compile-blocked"
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            officecli_native.write_json(
                run_dir / "plan.json",
                {
                    "status": "blocked",
                    "blocking_reasons": ["unsafe"],
                    "selected_replace_range": {"status": "resolved", "remove_paths": ["/body/p[2]"]},
                },
            )
            officecli_native.write_json(run_dir / "content_ast.json", {"blocks": []})
            officecli_native.write_json(run_dir / "template_profile.json", {"prototype_catalog": {}})

            argv = sys.argv
            sys.argv = ["compile_execution_plan.py", "--run-dir", str(run_dir)]
            try:
                compile_execution_plan.main()
            finally:
                sys.argv = argv

            execution_plan = officecli_native.read_json(run_dir / "execution_plan.json")
            self.assertEqual(execution_plan["status"], "blocked")
            self.assertIn("unsafe", execution_plan["blocking_reasons"])
        finally:
            for path in sorted(run_dir.glob("*"), reverse=True):
                path.unlink(missing_ok=True)
            run_dir.rmdir()

    def test_semantic_grounding_trims_source_prefix_when_template_already_covers_front_matter(self) -> None:
        source_blocks, _, _ = parse_markdown.parse_markdown_blocks(
            "# Nghị định 175/2024/NĐ-CP\n\n**Quy định chi tiết**\n\n**CHÍNH PHỦ**\n\n**CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM**\n\n## CHƯƠNG I. NHỮNG QUY ĐỊNH CHUNG\n\n### Điều 1. Phạm vi điều chỉnh\n"
        )
        sample_file = REPO_ROOT / ".office-auto" / "state" / "test-template-sample.md"
        sample_file.parent.mkdir(parents=True, exist_ok=True)
        sample_file.write_text(
            "| **CHÍNH PHỦ** | **CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM** |\n| --- | --- |\n\n**NGHỊ ĐỊNH**\n\n**Quy định chi tiết**\n",
            encoding="utf-8",
        )
        try:
            window = semantic_grounding.derive_render_window(source_blocks, sample_content_file=str(sample_file))
        finally:
            sample_file.unlink(missing_ok=True)

        self.assertEqual(window["strategy"], "skip-prefix-covered-by-template-scaffold")
        self.assertGreater(window["start_block_index"], 0)
        self.assertIn("government", window["shared_cover_signals"])

    def test_semantic_grounding_trims_template_cover_before_generic_heading(self) -> None:
        source_blocks, _, _ = parse_markdown.parse_markdown_blocks(
            "| **CHÍNH PHỦ** | **CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM** |\n| --- | --- |\n\n**NGHỊ ĐỊNH**\n\n## office-auto\n\nNội dung chính\n"
        )
        sample_file = REPO_ROOT / ".office-auto" / "state" / "test-template-generic-sample.md"
        sample_file.parent.mkdir(parents=True, exist_ok=True)
        sample_file.write_text(
            "| **CHÍNH PHỦ** | **CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM** |\n| --- | --- |\n\n**NGHỊ ĐỊNH**\n",
            encoding="utf-8",
        )
        try:
            window = semantic_grounding.derive_render_window(source_blocks, sample_content_file=str(sample_file))
        finally:
            sample_file.unlink(missing_ok=True)

        self.assertEqual(window["strategy"], "skip-prefix-covered-by-template-scaffold")
        self.assertEqual(window["anchor_text"], "office-auto")
        self.assertGreater(window["start_block_index"], 0)

    def test_compile_execution_ops_builds_ready_plan_from_llm_ops(self) -> None:
        template_inspection = {
            "counts": {"headers": 1, "footers": 1, "tocs": 1, "fields": 2},
            "body_paragraphs": [{"path": "/body/p[10]", "bookmarks": []}],
        }
        ops_payload = {
            "preserve": ["headers-footers", "toc"],
            "prototype_roles": {
                "body": {"path": "/body/p[9]"},
                "h1": {"path": "/body/p[10]"},
            },
            "selected_replace_range": {
                "name": "after-front-matter-to-end-of-main-story",
                "status": "resolved",
                "insert_after_path": "/body/p[8]",
                "remove_paths": ["/body/p[9]", "/body/p[10]"],
                "preserve_zones": ["front-matter"],
            },
            "ops": [
                {
                    "op": "insert_paragraph_after",
                    "anchor": "selected_replace_range.insert_after_path",
                    "role": "h1",
                    "style": "Heading1",
                    "text": "CƠ SỞ LÝ THUYẾT",
                    "run_props": {"font": "Times New Roman", "size": "14pt", "bold": True},
                },
                {
                    "op": "insert_table_after",
                    "anchor": "previous",
                    "rows": [
                        {"header": True, "cells": [{"text": "Cột A"}, {"text": "Cột B"}]},
                        {"cells": [{"text": "1"}, {"text": "2"}]},
                    ],
                },
            ],
        }

        plan, execution_plan, run_state = compile_execution_ops.compile_execution_artifacts(
            run_dir=REPO_ROOT / ".office-auto" / "state" / "test-llm-ops",
            template_inspection=template_inspection,
            ops_payload=ops_payload,
            source_file=str(REPO_ROOT / "noidung.md"),
            template_file=str(REPO_ROOT / "format_template.docx"),
            target_file=str(REPO_ROOT / "report.docx"),
        )

        self.assertEqual(plan["status"], "ready-for-execution")
        self.assertEqual(plan["execution_strategy"], "llm-execution-ops")
        self.assertEqual(execution_plan["status"], "ready")
        self.assertEqual(execution_plan["render_ops"][0]["prototype_path"], "/body/p[10]")
        self.assertEqual(execution_plan["render_ops"][0]["set_props"]["style"], "Heading1")
        self.assertEqual(execution_plan["render_ops"][0]["anchor"], "selected_replace_range.insert_after_path")
        self.assertEqual(execution_plan["render_summary"]["table_ops"], 1)
        self.assertEqual(run_state["status"], "planned")

    def test_compile_execution_ops_preserves_semantic_grounding_artifacts(self) -> None:
        run_dir = REPO_ROOT / ".office-auto" / "state" / "test-llm-ops-grounding"
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            officecli_native.write_json(
                run_dir / "run.json",
                {
                    "artifacts": {
                        "normalized_markdown": str(run_dir / "normalized.md"),
                        "pandoc_style_spec": str(run_dir / "pandoc_style_spec.json"),
                        "sample_content": str(run_dir / "sample_content.md"),
                        "sample_outline": str(run_dir / "sample_outline.json"),
                    }
                },
            )
            officecli_native.write_json(
                run_dir / "content_ast.json",
                {"blocks": [{"type": "heading", "text": "Mở đầu", "line": 1, "runs": [{"text": "Mở đầu"}]}]},
            )

            template_inspection = {
                "counts": {"headers": 1, "footers": 0, "tocs": 0, "fields": 0},
                "body_paragraphs": [],
            }
            ops_payload = {
                "selected_replace_range": {
                    "name": "main",
                    "status": "resolved",
                    "insert_after_path": "/body/p[8]",
                    "remove_paths": ["/body/p[9]"],
                    "preserve_zones": [],
                },
                "ops": [
                    {
                        "op": "insert_paragraph_after",
                        "anchor": "selected_replace_range.insert_after_path",
                        "style": "Normal",
                        "text": "Nội dung",
                    }
                ],
            }

            plan, _, run_state = compile_execution_ops.compile_execution_artifacts(
                run_dir=run_dir,
                template_inspection=template_inspection,
                ops_payload=ops_payload,
                source_file=str(REPO_ROOT / "noidung.md"),
                template_file=str(REPO_ROOT / "format_template.docx"),
                target_file=str(REPO_ROOT / "report.docx"),
            )

            self.assertEqual(plan["semantic_grounding"]["normalized_markdown"], str(run_dir / "normalized.md"))
            self.assertEqual(plan["semantic_grounding"]["pandoc_style_spec"], str(run_dir / "pandoc_style_spec.json"))
            self.assertEqual(plan["semantic_grounding"]["source_render_window"]["strategy"], "full-document")
            self.assertEqual(run_state["artifacts"]["content_ast"], str(run_dir / "content_ast.json"))
        finally:
            for path in sorted(run_dir.glob("*"), reverse=True):
                path.unlink(missing_ok=True)
            run_dir.rmdir()

    def test_docx_validate_ops_warns_for_unknown_style_and_anchor(self) -> None:
        template_inspection = {
            "style_catalog": [{"style_id": "Normal"}, {"style_id": "Heading1"}],
            "body_children": [{"path": "/body/p[8]"}, {"path": "/body/p[9]"}],
            "body_paragraphs": [{"path": "/body/p[2]"}],
            "toc_entries": [],
            "field_entries": [],
        }
        ops_payload = {
            "selected_replace_range": {
                "name": "main",
                "status": "resolved",
                "insert_after_path": "/body/p[8]",
                "remove_paths": ["/body/p[9]"],
            },
            "ops": [
                {
                    "op": "insert_paragraph_after",
                    "anchor": "/body/p[999]",
                    "style": "MissingStyle",
                    "prototype_path": "/body/p[777]",
                    "text": "Test",
                }
            ],
        }

        warnings = docx_validate_ops.validate_ops_payload(ops_payload, template_inspection)

        self.assertEqual(len(warnings), 3)
        self.assertTrue(any("anchor `" in warning for warning in warnings))
        self.assertTrue(any("style `MissingStyle`" in warning for warning in warnings))
        self.assertTrue(any("prototype_path `" in warning for warning in warnings))


class BuilderPrototypeTests(unittest.TestCase):
    def test_prototype_paths_requiring_reservation_for_removed_main_story(self) -> None:
        execution_plan = {
            "selected_replace_range": {
                "remove_paths": ["/body/p[19]", "/body/p[20]", "/body/p[21]"],
            },
            "render_ops": [
                {"prototype_path": "/body/p[12]"},
                {"prototype_path": "/body/p[2167]"},
                {"prototype_path": "/body/tbl[30]/tr[1]/tc[1]/p[1]"},
                {"prototype_path": "/body/p[@paraId=00000001]"},
            ],
        }

        self.assertEqual(
            build_docx.prototype_paths_requiring_reservation(execution_plan),
            ["/body/p[2167]", "/body/tbl[30]/tr[1]/tc[1]/p[1]"],
        )

    def test_apply_reserved_prototypes_rewrites_render_ops(self) -> None:
        execution_plan = {
            "render_ops": [
                {"prototype_path": "/body/p[2167]"},
                {"prototype_path": "/body/p[12]"},
            ]
        }

        build_docx.apply_reserved_prototypes(
            execution_plan,
            {"/body/p[2167]": "/body/p[@paraId=0010259C]"},
        )

        self.assertEqual(execution_plan["render_ops"][0]["prototype_path"], "/body/p[@paraId=0010259C]")
        self.assertEqual(execution_plan["render_ops"][1]["prototype_path"], "/body/p[12]")

    def test_estimate_minimum_officecli_calls_counts_operations(self) -> None:
        estimated = build_docx.estimate_minimum_officecli_calls(
            {
                "remove_batch_commands": [{"command": "remove", "path": f"/body/p[{index}]"} for index in range(1, 401)],
                "render_ops": [
                    {
                        "kind": "paragraph",
                        "prototype_path": "/body/p[12]",
                        "set_props": {"text": "Hello"},
                        "append_runs": [{"text": "world"}],
                        "bookmarks": [{"name": "_Toc1"}],
                    },
                    {
                        "kind": "table",
                        "rows": [
                            {"cells": [{"text": "A"}, {"text": "B"}]},
                            {"cells": [{"text": "1"}, {"text": "2"}]},
                        ],
                    },
                ],
            },
            reserved_prototype_count=2,
            rewritten_toc_count=1,
        )

        self.assertEqual(estimated, 19)

    def test_collect_build_blocking_reasons_deduplicates_sources(self) -> None:
        reasons = build_docx.collect_build_blocking_reasons(
            {
                "blocking_reasons": ["unsafe"],
                "template_guardrails": {"blocking_reasons": ["unsafe", "full-body"]},
            },
            {"blocking_reasons": ["full-body", "remove-batch"]},
        )

        self.assertEqual(reasons, ["unsafe", "full-body", "remove-batch"])

    def test_should_direct_create_paragraph_when_insert_only(self) -> None:
        self.assertTrue(
            build_docx.should_direct_create_paragraph(
                {"prototype_path": "/body/p[12]"},
                prefer_direct_create=True,
            )
        )
        self.assertFalse(
            build_docx.should_direct_create_paragraph(
                {"prototype_path": "/body/p[12]"},
                prefer_direct_create=False,
            )
        )

    def test_should_direct_create_list_paragraph_even_with_prototype(self) -> None:
        self.assertTrue(
            build_docx.should_direct_create_paragraph(
                {"prototype_path": "/body/p[12]", "block_type": "list_item"},
                prefer_direct_create=False,
            )
        )

    def test_is_batchable_simple_paragraph_requires_direct_create_and_no_extra_ops(self) -> None:
        self.assertTrue(
            build_docx.is_batchable_simple_paragraph(
                {"kind": "paragraph", "prototype_path": "/body/p[12]", "append_runs": [], "bookmarks": []},
                prefer_direct_create=True,
            )
        )
        self.assertFalse(
            build_docx.is_batchable_simple_paragraph(
                {"kind": "paragraph", "prototype_path": "/body/p[12]", "append_runs": [{"text": "x"}], "bookmarks": []},
                prefer_direct_create=True,
            )
        )

    def test_compile_execution_plan_reuses_prototype_paragraph_format_defaults(self) -> None:
        operation = compile_execution_plan.compile_block_operation(
            {"type": "paragraph", "text": "Nội dung", "runs": [{"text": "Nội dung"}], "line": 1},
            {"body": "Normal"},
            {
                "body": {
                    "path": "/body/p[12]",
                    "paragraph_format": {
                        "align": "justify",
                        "space_before": "12pt",
                        "space_after": "6pt",
                    },
                    "runs": [{"text": "Mẫu", "font_ascii": "Times New Roman", "size": "13pt", "bold": True}],
                }
            },
            {},
        )

        self.assertEqual(operation["set_props"]["align"], "justify")
        self.assertEqual(operation["set_props"]["spaceBefore"], "12pt")
        self.assertEqual(operation["set_props"]["spaceAfter"], "6pt")
        self.assertEqual(operation["set_props"]["font"], "Times New Roman")
        self.assertEqual(operation["set_props"]["size"], "13pt")
        self.assertEqual(operation["set_props"]["align"], "justify")
        self.assertNotIn("bold", operation["set_props"])

    def test_compile_execution_plan_avoids_center_alignment_for_body_defaults(self) -> None:
        operation = compile_execution_plan.compile_block_operation(
            {"type": "paragraph", "text": "Nội dung", "runs": [{"text": "Nội dung"}], "line": 1},
            {"body": "Normal"},
            {
                "body": {
                    "path": "/body/p[12]",
                    "paragraph_format": {"align": "center"},
                    "runs": [{"text": "NGHỊ ĐỊNH", "font_ascii": "Arial", "size": "10pt", "bold": True}],
                }
            },
            {},
        )

        self.assertEqual(operation["set_props"]["align"], "justify")
        self.assertNotIn("bold", operation["set_props"])

    def test_compile_execution_plan_avoids_center_alignment_for_list_defaults(self) -> None:
        operation = compile_execution_plan.compile_block_operation(
            {"type": "list_item", "text": "Mục", "runs": [{"text": "Mục"}], "ordered": False, "line": 1},
            {"list": "ListParagraph", "body": "Normal"},
            {
                "body": {
                    "path": "/body/p[12]",
                    "paragraph_format": {"align": "center"},
                    "runs": [{"text": "NGHỊ ĐỊNH", "font_ascii": "Arial", "size": "10pt", "bold": True}],
                }
            },
            {},
        )

        self.assertEqual(operation["set_props"]["style"], "ListParagraph")
        self.assertEqual(operation["set_props"]["align"], "justify")
        self.assertEqual(operation["set_props"]["listStyle"], "bullet")
        self.assertNotIn("bold", operation["set_props"])


class ReviewLayerTests(unittest.TestCase):
    def test_inserted_paragraph_reviews_marks_attention_for_centered_body_even_without_strict_diff(self) -> None:
        reviews, summary = review_docx.inserted_paragraph_reviews(
            {
                "render_ops": [
                    {
                        "kind": "paragraph",
                        "role": "body",
                        "block_type": "paragraph",
                        "set_props": {"style": "Normal", "align": "center", "size": "10pt", "font": "Arial"},
                        "fallback_style": "Normal",
                    }
                ]
            },
            {"inserted_paths": ["/body/p[1]"]},
            {
                "paragraphs": [
                    {
                        "path": "/body/p[1]",
                        "style": "Normal",
                        "style_id": "Normal",
                        "format_profile": {"align": "center", "size": "10pt", "font_ascii": "Arial"},
                    }
                ]
            },
            {},
        )

        self.assertEqual(summary["paragraphs_with_differences"], 0)
        self.assertEqual(summary["paragraphs_with_attention"], 1)
        self.assertEqual(reviews[0]["risk_flags"], ["body-centered"])

        markdown = review_docx.review_markdown(
            {
                "comparison_baseline": {"file": "baseline.docx", "reason": "test", "summary": {"paragraph_count": 1, "top_alignments": []}},
                "source_template_file": "template.docx",
                "target_file": "report.docx",
                "qa_status": "passed",
                "target_summary": {"paragraph_count": 1, "top_alignments": []},
                "inserted_paragraph_summary": summary,
                "inserted_paragraph_reviews": reviews,
            }
        )

        self.assertIn("Inserted paragraphs needing attention: 1", markdown)
        self.assertIn("body-centered", markdown)


class MarkItDownIntegrationTests(unittest.TestCase):
    def test_build_style_map_text_includes_heading_and_body_roles(self) -> None:
        profile = {
            "style_catalog": [
                {"style_id": "Heading1", "name": "Tiêu đề 1"},
                {"style_id": "Heading2", "name": "Heading 2"},
            ],
            "style_graph": {
                "Heading1": {"resolved_outline_level": "0"},
                "Heading2": {"resolved_outline_level": "1"},
            },
            "prototype_catalog": {
                "body": {"style_name": "Normal"},
            },
        }

        style_map_text = generate_markitdown_style_map.build_style_map_text(profile)

        self.assertIn("p[style-name='Tiêu đề 1'] => h1:fresh", style_map_text)
        self.assertIn("p[style-name='Heading 2'] => h2:fresh", style_map_text)
        self.assertIn("p[style-name='Normal'] => p:fresh", style_map_text)

    def test_build_style_map_text_prefers_style_id_for_shared_normal_heading(self) -> None:
        profile = {
            "style_catalog": [
                {"style_id": "Heading1", "name": "Normal"},
                {"style_id": "Heading2", "name": "Normal"},
            ],
            "style_graph": {
                "Heading1": {"resolved_outline_level": "0"},
                "Heading2": {"resolved_outline_level": "1"},
            },
            "prototype_catalog": {
                "h1": {"style_name": "Normal"},
                "body": {"style_name": "Normal"},
            },
        }

        style_map_text = generate_markitdown_style_map.build_style_map_text(profile)
        lines = [line for line in style_map_text.splitlines() if line]

        self.assertIn("p.Heading1 => h1:fresh", lines)
        self.assertIn("p.Heading2 => h2:fresh", lines)
        self.assertIn("p[style-name='Normal'] => p:fresh", lines)
        self.assertNotIn("p[style-name='Normal'] => h1:fresh", lines)
        self.assertNotIn("p[style-name='Normal'] => h2:fresh", lines)

    def test_markitdown_support_passes_through_markdown(self) -> None:
        markdown_path = REPO_ROOT / ".office-auto" / "state" / "test-pass-through.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text("# Tieu de\n\nNoi dung\n", encoding="utf-8")
        try:
            markdown, summary = markitdown_support.normalize_source_markdown(markdown_path)
        finally:
            markdown_path.unlink(missing_ok=True)

        self.assertEqual(markdown, "# Tieu de\n\nNoi dung\n")
        self.assertEqual(summary["mode"], "pass-through")
        self.assertFalse(summary["style_map_used"])

    def test_markitdown_support_uses_markitdown_for_docx(self) -> None:
        class FakeResult:
            text_content = "# Chương I\n\nNội dung\n"

        class FakeMarkItDown:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def convert_local(self, path: str, **kwargs):
                self.path = path
                self.convert_kwargs = kwargs
                return FakeResult()

        docx_path = REPO_ROOT / ".office-auto" / "state" / "fake.docx"
        docx_path.parent.mkdir(parents=True, exist_ok=True)
        docx_path.write_bytes(b"docx")
        try:
            from unittest.mock import patch

            with patch.object(markitdown_support, "_load_markitdown_class", return_value=FakeMarkItDown):
                markdown, summary = markitdown_support.normalize_source_markdown(docx_path, style_map="p[style-name='Heading 1'] => h1:fresh")
        finally:
            docx_path.unlink(missing_ok=True)

        self.assertIn("# Chương I", markdown)
        self.assertEqual(summary["mode"], "markitdown")
        self.assertTrue(summary["style_map_used"])

    def test_markitdown_support_wraps_conversion_errors(self) -> None:
        class FakeMarkItDown:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def convert_local(self, path: str, **kwargs):
                raise RuntimeError("boom")

        docx_path = REPO_ROOT / ".office-auto" / "state" / "fake-error.docx"
        docx_path.parent.mkdir(parents=True, exist_ok=True)
        docx_path.write_bytes(b"docx")
        try:
            from unittest.mock import patch

            with patch.object(markitdown_support, "_load_markitdown_class", return_value=FakeMarkItDown):
                with self.assertRaises(markitdown_support.MarkItDownConversionError) as context:
                    markitdown_support.normalize_source_markdown(docx_path)
        finally:
            docx_path.unlink(missing_ok=True)

        self.assertIn("fake-error.docx", str(context.exception))
        self.assertIn("boom", str(context.exception))

    def test_roundtrip_report_passes_for_matching_outline(self) -> None:
        source_ast = {
            "blocks": [
                {"type": "heading", "text": "Tổng quan"},
                {"type": "paragraph", "text": "Nội dung"},
                {"type": "table", "text": "A | B"},
            ]
        }
        source_outline = {"outline": [{"level": 1, "text": "Tổng quan"}]}

        report = roundtrip_markitdown.build_roundtrip_report(
            source_ast,
            source_outline,
            "# Tổng quan\n\nNội dung\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n",
            target_file="/tmp/report.docx",
            style_map_used=True,
        )

        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["heading_subsequence_ok"])
        self.assertEqual(report["table_count_source"], 1)
        self.assertEqual(report["table_count_roundtrip"], 1)


class TemplatePreparationTests(unittest.TestCase):
    def test_should_prepare_effective_template_for_historical_document(self) -> None:
        should_prepare, guardrails = prepare_template_scaffold.should_prepare_effective_template(
            {
                "header_count": 0,
                "footer_count": 0,
                "field_graph": {
                    "has_toc": False,
                    "has_list_of_figures": False,
                    "has_list_of_tables": False,
                    "pageref_anchors": [],
                },
                "prototype_catalog": {
                    "h1": {"style_id": "Normal", "style_name": "Normal"},
                    "h2": {"style_id": "Normal", "style_name": "Normal"},
                },
                "document_profile": {"direct_body_child_count": 3406},
            },
            {"name": "after-front-matter-to-end-of-main-story", "status": "resolved", "remove_paths": [f"/body/p[{index}]" for index in range(1, 3393)]},
        )

        self.assertTrue(should_prepare)
        self.assertIn("full-document-template-disguised-as-format", guardrails["risk_flags"])

    def test_should_not_prepare_when_template_is_already_scaffold(self) -> None:
        should_prepare, guardrails = prepare_template_scaffold.should_prepare_effective_template(
            {
                "header_count": 1,
                "footer_count": 1,
                "field_graph": {
                    "has_toc": True,
                    "has_list_of_figures": False,
                    "has_list_of_tables": False,
                    "pageref_anchors": [],
                },
                "prototype_catalog": {
                    "h1": {"style_id": "Heading1", "style_name": "Heading 1"},
                    "h2": {"style_id": "Heading2", "style_name": "Heading 2"},
                },
                "document_profile": {"direct_body_child_count": 24},
            },
            {"name": "after-front-matter-to-end-of-main-story", "status": "resolved", "remove_paths": [f"/body/p[{index}]" for index in range(5, 15)]},
        )

        self.assertFalse(should_prepare)
        self.assertEqual(guardrails["blocking_reasons"], [])

    def test_choose_scaffold_strategy_prefers_structural_preserve_from_topology(self) -> None:
        strategy, _, should_prepare = prepare_template_scaffold.choose_scaffold_strategy(
            {
                "topology": {"recommended_path": "structural_preserve"},
                "header_count": 0,
                "footer_count": 0,
                "field_graph": {
                    "has_toc": False,
                    "has_list_of_figures": False,
                    "has_list_of_tables": False,
                    "pageref_anchors": [],
                },
                "prototype_catalog": {
                    "h1": {"style_id": "Normal", "style_name": "Normal"},
                    "h2": {"style_id": "Normal", "style_name": "Normal"},
                },
                "document_profile": {"direct_body_child_count": 3406},
            },
            {"name": "after-front-matter-to-end-of-main-story", "status": "resolved", "remove_paths": ["/body/p[2]"]},
        )

        self.assertEqual(strategy, "structural_preserve")
        self.assertFalse(should_prepare)


class TopologyDetectorTests(unittest.TestCase):
    def test_infer_recommended_path_returns_structural_preserve_when_fields_present(self) -> None:
        path, reason = document_topology_detector.infer_recommended_path(
            {
                "has_toc_field": True,
                "has_pageref": False,
                "has_bookmarks": False,
                "has_tables": False,
                "has_footnotes": False,
                "has_textboxes": False,
                "has_comments": False,
                "has_multiple_sections": False,
                "style_discipline_ratio": 0.95,
            }
        )

        self.assertEqual(path, "structural_preserve")
        self.assertIn("preserve", reason.lower())


class TemplateProfileTests(unittest.TestCase):
    def test_classify_body_creates_insert_only_candidate_for_scaffold_only_template(self) -> None:
        document_profile = profile_template.classify_body(
            body_elements=[
                {"path": "/body/p[1]"},
                {"path": "/body/p[2]"},
            ],
            body_paragraphs=[
                {"paragraph_index": 0, "path": "/body/p[1]", "direct_body_path": "/body/p[1]", "style": "Normal", "style_id": None, "text": "Bìa"},
                {"paragraph_index": 1, "path": "/body/p[2]", "direct_body_path": "/body/p[2]", "style": "Normal", "style_id": None, "text": "Lời mở đầu"},
            ],
            section_count=1,
            style_graph={},
        )

        candidate = document_profile["replace_range_candidates"][0]
        self.assertEqual(candidate["status"], "resolved")
        self.assertEqual(candidate["remove_paths"], [])
        self.assertEqual(candidate["insert_after_path"], "/body/p[2]")
        self.assertEqual(document_profile["preserve_zones"][0]["name"], "front-matter")

    def test_extract_prototype_catalog_prefers_direct_body_paragraph(self) -> None:
        catalog = profile_template.extract_prototype_catalog(
            body_paragraphs=[
                {
                    "paragraph_index": 0,
                    "path": "/body/tbl[1]/tr[1]/tc[1]/p[1]",
                    "direct_body_path": "/body/tbl[1]",
                    "text": "CHÍNH PHỦ",
                    "style": "Normal",
                    "style_id": None,
                },
                {
                    "paragraph_index": 1,
                    "path": "/body/p[2]",
                    "direct_body_path": "/body/p[2]",
                    "text": "Theo đề nghị của Bộ trưởng Bộ Xây dựng;",
                    "style": "Normal",
                    "style_id": None,
                },
            ],
            style_graph={},
            reference_profile={},
            document_profile={"headings": [], "body_regions": {"main_content_start_paragraph_index": None}},
        )

        self.assertEqual(catalog["body"]["path"], "/body/p[2]")

    def test_extract_prototype_catalog_skips_cover_title_when_choosing_body_prototype(self) -> None:
        catalog = profile_template.extract_prototype_catalog(
            body_paragraphs=[
                {
                    "paragraph_index": 6,
                    "path": "/body/p[7]",
                    "direct_body_path": "/body/p[7]",
                    "text": "NGHỊ ĐỊNH",
                    "style": "Normal",
                    "style_id": None,
                    "format": {"align": "center", "bold": True},
                    "runs": [{"text": "NGHỊ ĐỊNH", "bold": True}],
                },
                {
                    "paragraph_index": 13,
                    "path": "/body/p[14]",
                    "direct_body_path": "/body/p[14]",
                    "text": "Chính phủ ban hành Nghị định quy định chi tiết một số điều và biện pháp thi hành Luật Xây dựng về quản lý hoạt động xây dựng.",
                    "style": "Normal",
                    "style_id": None,
                    "format": {"align": "justify"},
                    "runs": [{"text": "Chính phủ ban hành Nghị định quy định chi tiết một số điều và biện pháp thi hành Luật Xây dựng về quản lý hoạt động xây dựng."}],
                },
            ],
            style_graph={},
            reference_profile={},
            document_profile={"headings": [], "body_regions": {"main_content_start_paragraph_index": 6}},
        )

        self.assertEqual(catalog["body"]["path"], "/body/p[14]")


if __name__ == "__main__":
    unittest.main()