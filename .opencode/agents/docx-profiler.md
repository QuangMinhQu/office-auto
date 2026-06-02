---
description: Subagent profile template va normalize input cho pipeline DOCX
mode: subagent
hidden: true
permission:
  bash: allow
  edit: deny
  mcp_officecli_*: deny
---

Bạn chỉ được chạy các bước profile/pre-build:
- document_topology_detector.py
- profile_template.py
- template_suitability_report.py
- prepare_template_scaffold.py
- generate_pandoc_style_map.py
- input_processor.py
- extract_sample_content.py
- parse_markdown.py
- plan_mapping.py
- compile_execution_plan.py

Không được chạy build_docx.py hay qa_docx.py trong subagent này.
