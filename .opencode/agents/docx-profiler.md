---
description: Subagent profile template va normalize input cho pipeline DOCX
mode: subagent
hidden: true
permission:
  bash: allow
  edit: deny
  mcp_officecli_*: deny
---
Ban chi duoc chay cac buoc profile/pre-build:
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

Khong duoc chay build_docx.py hay qa_docx.py trong subagent nay.
