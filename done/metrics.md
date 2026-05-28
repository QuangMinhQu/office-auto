Đánh giá một hệ thống **agentic document automation** (tự động sinh/chỉnh sửa `.docx`, `.pptx`, `.xlsx` từ task-level instruction) là một bài toán khá phức tạp, vì bạn không chỉ đánh giá output cuối cùng mà còn phải đánh giá:

* planning quality,
* tool orchestration,
* document structure integrity,
* semantic correctness,
* execution reliability,
* human usability,
* và cả long-horizon task completion.

Về bản chất, đây là sự giao thoa giữa:

* NLP evaluation,
* software agent evaluation,
* HCI/document usability,
* workflow automation benchmarking.

Một framework đánh giá tốt thường cần chia thành nhiều tầng metric.

---

# I. Phân rã bài toán đúng cách

Trước tiên cần hiểu pipeline dạng:

```text
User Goal
   ↓
Task Planning Agent
   ↓
Tool Invocation / APIs
   ↓
Document Editing Actions
   ↓
Generated Office Artifacts
   ↓
Human Consumption
```

Cho nên metric không thể chỉ là:

> “output có đẹp không”

mà phải đánh giá:

1. Goal completion
2. Structural correctness
3. Semantic fidelity
4. Formatting quality
5. Execution robustness
6. Agent reasoning quality
7. Efficiency / cost
8. Human satisfaction

---

# II. Nhóm metric cốt lõi

# 1. Task Success Metrics (quan trọng nhất)

Đây là tầng cao nhất.

## 1.1 Goal Completion Rate (GCR)

Metric cơ bản:

[
GCR = \frac{\text{Tasks completed successfully}}{\text{Total tasks}}
]

Ví dụ:

* “Tạo báo cáo doanh thu quý”
* “Sinh slide pitch deck”
* “Tạo Excel forecast với chart”

Nếu output đáp ứng đầy đủ yêu cầu → success.

---

## 1.2 Requirement Coverage Score

Đo mức độ coverage của instruction.

Ví dụ instruction:

```text
- 10 slides
- include bar chart
- blue theme
- executive summary
- financial table
```

Agent có thể:

| Requirement       | Covered |
| ----------------- | ------- |
| 10 slides         | ✓       |
| bar chart         | ✓       |
| blue theme        | ✗       |
| executive summary | ✓       |
| financial table   | ✓       |

Coverage:

[
Coverage = \frac{4}{5}=0.8
]

Rất quan trọng trong agentic systems.

---

## 1.3 Constraint Satisfaction

Đánh giá agent có tuân thủ constraint không:

Ví dụ:

* font size
* company template
* slide limit
* no hallucinated numbers
* formulas preserved
* formatting policy

Đây gần giống SAT verification.

---

# III. Document Quality Metrics

---

# 2. Semantic Fidelity

## 2.1 Content Accuracy

Đánh giá factual correctness.

Ví dụ:

* số liệu trong Excel đúng?
* chart đúng dữ liệu?
* summary có bịa không?

Thường dùng:

* human eval
* retrieval verification
* schema validation
* formula checking

---

## 2.2 Instruction Following Score

LLM-as-a-judge thường dùng.

Prompt judge:

```text
Given the instruction and produced document,
score from 1-10 how well the document follows instructions.
```

Có thể dùng pairwise ranking:

* Agent A vs Agent B

---

## 2.3 Hallucination Rate

Đặc biệt quan trọng với:

* business reports
* financial documents
* research slides

Ví dụ:

[
Hallucination\ Rate =
\frac{\text{Unsupported claims}}{\text{Total claims}}
]

---

# 3. Structural Integrity Metrics

Đây là phần mà nhiều benchmark hiện tại thiếu.

---

## 3.1 Office Structural Validity

Đánh giá file có đúng chuẩn Office XML không.

Ví dụ:

### DOCX

* paragraph tree valid?
* style refs broken?
* table corrupted?

### PPTX

* slide master valid?
* embedded chart valid?
* animation refs broken?

### XLSX

* formulas parse được?
* workbook relationship valid?
* chart objects intact?

Có thể parse bằng:

* python-docx
* openpyxl
* pptx
* OOXML validators

---

## 3.2 Formatting Consistency Score

Ví dụ:

* font consistency
* spacing consistency
* theme coherence
* alignment regularity

Có thể đo bằng entropy:

[
Consistency = 1 - H(styles)
]

---

## 3.3 Layout Quality

Đặc biệt cho PPTX.

Metrics:

* overlap rate
* off-slide elements
* whitespace balance
* text overflow

Computer vision + layout analysis thường dùng.

---

# IV. Spreadsheet-Specific Metrics (XLSX)

Spreadsheet khó hơn nhiều.

---

# 4. Formula Correctness

Quan trọng nhất.

Ví dụ:

```excel
=SUM(B2:B10)
```

có đúng logic không?

Có thể đánh giá:

* execution equivalence
* formula graph similarity
* dependency graph accuracy

---

## 4.1 Computational Accuracy

Đo output numeric cuối cùng.

[
Accuracy =
\frac{\text{Correct cells}}{\text{Total evaluated cells}}
]

---

## 4.2 Spreadsheet Dependency Integrity

Spreadsheet thực chất là DAG.

Agent tốt phải preserve:

* references
* formula lineage
* dependency graph

Có thể compare graph edit distance.

---

# V. Presentation-Specific Metrics (PPTX)

---

# 5. Slide Communication Quality

Không chỉ đẹp mà còn communication effectiveness.

Metrics:

## 5.1 Information Density

Quá ít → vô dụng
Quá nhiều → unreadable

---

## 5.2 Visual Hierarchy Score

Đo:

* title prominence
* alignment
* typography structure

---

## 5.3 Narrative Coherence

Slide deck có storytelling logic không?

Ví dụ:

```text
Problem
→ Market
→ Solution
→ Product
→ Revenue
→ Ask
```

Có thể dùng discourse analysis.

---

# VI. Agentic Workflow Metrics

Đây là phần quan trọng nhất nếu bạn nghiên cứu AI Agents.

---

# 6. Planning Metrics

## 6.1 Plan Optimality

Ví dụ:

Task cần 5 bước nhưng agent dùng 23 tool calls.

Đo:

[
Efficiency =
\frac{\text{Optimal steps}}{\text{Actual steps}}
]

---

## 6.2 Tool Selection Accuracy

Agent có chọn đúng tool không?

Ví dụ:

* dùng Excel API thay vì OCR
* dùng chart API thay vì screenshot

---

## 6.3 Recovery Capability

Khi tool fail:

* retry?
* fallback?
* self-correction?

Đây là metric rất mạnh cho autonomous agents.

---

# 7. Execution Reliability

## 7.1 Runtime Failure Rate

[
Failure\ Rate =
\frac{\text{Crashed tasks}}{\text{Total tasks}}
]

---

## 7.2 Determinism / Stability

Cùng input:

* output có consistent không?
* format có drift không?

---

## 7.3 Long-Horizon Stability

Task 50–100 actions:

* context drift?
* forgotten objectives?
* file corruption accumulation?

Rất quan trọng với multi-agent systems.

---

# VII. Human-Centered Metrics

---

# 8. Human Usability

Cuối cùng document là để con người dùng.

## 8.1 Edit Distance to Human Acceptance

Metric cực thực tế:

> Human cần sửa bao nhiêu trước khi dùng được?

Ví dụ:

* số thao tác edit
* time-to-finalization

---

## 8.2 User Satisfaction

Likert scale:

* readability
* usefulness
* professionalism

---

## 8.3 Cognitive Load

Người dùng có cần:

* sửa nhiều?
* debug file?
* reformat lại?

---

# VIII. Một framework evaluation thực tế

Nếu tôi build benchmark cho hệ này, tôi sẽ chia:

| Layer       | Metrics                           |
| ----------- | --------------------------------- |
| Goal        | Success rate, coverage            |
| Semantics   | factuality, instruction following |
| Structure   | OOXML validity, layout            |
| Spreadsheet | formula correctness               |
| Agent       | planning efficiency, tool usage   |
| Reliability | crash rate, stability             |
| Human       | edit distance, preference         |

---

# IX. Các benchmark/research liên quan

Hiện có vài benchmark rất đáng tham chiếu, nhưng mỗi benchmark chỉ cover một phần của bài toán office agent.

| Benchmark | Cover tốt phần nào | Phần có thể mượn cho repo này | Điểm còn thiếu với bài toán office artifact |
| --- | --- | --- | --- |
| SheetCopilot | Spreadsheet action execution, ground-truth workbook checking, log trajectory | Cách định nghĩa action-level oracle, nhiều ground truth cho một task, log YAML per run | Gần như chỉ mạnh ở spreadsheet; không cover DOCX/PPTX scaffold integrity |
| WebArena | Multi-step realistic tasks, execution-based validation trong môi trường web | Tư duy validator theo task intent, tách answer-check và state-check | Không chấm OOXML structure hay formatting quality |
| OSWorld | Real computer tasks, cross-app workflow, execution-based eval, reproducible task setup | Cách đóng gói task với initial state + evaluator script + trajectory replay | Quá rộng và nặng; không có oracle chuyên biệt cho DOCX/PPTX/XLSX |
| AgentBench | Multi-turn agent evaluation qua nhiều môi trường và hành động | Ý tưởng đo planning, tool-use, failure handling, long-horizon completion | Artifact cuối không phải trọng tâm, nên thiếu file-quality metrics |
| GAIA | Trợ lý tổng quát với task khó, dài hơi, nhiều bước | Thích hợp để stress-test reasoning và decomposition | Chủ yếu chấm answer/task outcome, không chấm document/package integrity |
| DocVQA | Document understanding và question answering trên tài liệu | Dùng để tạo sub-benchmark cho document reading / evidence extraction | Không đo document editing hay preserve-template behavior |
| ChartQA | Chart reasoning, visual + logical QA | Tốt cho subskill đánh giá chart correctness / chart understanding | Không phải benchmark workflow tạo slide hoặc workbook hoàn chỉnh |

Tóm lại, chưa có benchmark chuẩn hóa hoàn chỉnh cho:

> Multi-agent Office document generation systems with structure-preserving edits

Research gap thực sự nằm ở chỗ phải chấm cùng lúc:

* final artifact quality,
* execution trajectory,
* tool correctness,
* và human correction cost.

---

# X. Metric quan trọng nhất thực tế

Nếu deploy production:

## DOCX

* instruction following
* formatting consistency
* human edit distance

## PPTX

* narrative coherence
* layout quality
* presentation effectiveness

## XLSX

* formula correctness
* dependency integrity
* numerical accuracy

## Agent System

* recovery capability
* long-horizon stability
* tool efficiency

---

# XI. Metric “đúng bản chất AGENT”

Nhiều người đánh giá sai vì chỉ nhìn output cuối.

Agent systems cần thêm:

[
Agent\ Quality
\neq
Output\ Quality
]

Một agent có thể:

* output đúng nhờ may mắn,
* nhưng planning tệ,
* retry nhiều,
* cost cao,
* unstable.

Cho nên cần đánh giá:

```text
Trajectory Quality
+
Tool Usage Quality
+
Recovery Quality
+
Final Artifact Quality
```

chứ không chỉ artifact cuối cùng.

---

# XII. Hướng advanced hơn (research-grade)

Nếu bạn muốn nghiên cứu nghiêm túc, có thể xây:

## Composite Utility Function

[
U =
\alpha S_{goal}
+
\beta S_{semantic}
+
\gamma S_{structure}
+
\delta S_{efficiency}
+
\epsilon S_{human}
]

hoặc dùng:

* Pareto frontier evaluation
* multi-objective optimization
* learned reward models
* human preference models

rất giống RLHF nhưng cho office agents.

---

# XIII. Kết luận

Một hệ thống agent tự động soạn `.docx/.pptx/.xlsx` nên được đánh giá ở 6 tầng:

1. **Task Completion**
2. **Semantic Correctness**
3. **Structural/Formatting Integrity**
4. **Agent Planning & Tool Use**
5. **Robustness & Stability**
6. **Human Usability**

Và với research-grade evaluation, phần quan trọng nhất thường là:

```text
Trajectory quality + artifact quality + human correction cost
```

vì đó mới phản ánh đúng năng lực của autonomous office agents.

---

# XIV. Evaluation plan cụ thể cho repo này

Nếu áp dụng ngay cho hệ trong repo này, tôi sẽ không đánh giá theo kiểu một điểm tổng duy nhất ngay từ đầu. Thay vào đó, benchmark nên đi theo 3 tầng:

## Tầng A. Hard-gate correctness

Task chỉ được xem là **pass kỹ thuật** nếu qua hết các điều kiện cứng sau:

* artifact mở được và không corrupt
* validator/tool parser pass
* không còn placeholder/template residue
* đúng mode chỉnh sửa mong muốn: preserve scaffold, replace bounded ranges, hoặc append section
* các phần preserve của template vẫn còn nguyên
* không xuất hiện duplicate heading/chapter pattern do regenerate sai

Đây là tầng đặc biệt quan trọng cho repo này vì pipeline đang tối ưu theo hướng **preserve-template-scaffold** chứ không phải regenerate toàn bộ.

## Tầng B. Task-level success

Sau khi qua hard gate mới chấm tiếp:

* requirement coverage
* semantic fidelity
* formatting/layout adherence
* tool-use efficiency

## Tầng C. Human acceptance

Cuối cùng mới đo:

* số phút sửa tay để dùng được
* số edit thủ công cần thiết
* mức chấp nhận của reviewer

---

# XV. Benchmark suite đề xuất

Nên tạo benchmark riêng gồm 4 nhóm task, vì mỗi nhóm làm lộ ra một failure mode khác nhau.

## 15.1 DOCX scaffold-preserving edits

Task mẫu:

* thay nội dung một chương từ markdown vào template có sẵn
* giữ nguyên bìa, mục lục, section break, numbering, heading map
* thêm phần tài liệu tham khảo đúng style template
* cập nhật bảng/hình/chú thích mà không phá cấu trúc tài liệu

Metric trọng tâm:

* replace-range resolution rate
* preserve-part integrity
* TOC/bookmark/reference correctness
* reference-format adherence

## 15.2 DOCX append/fill tasks

Task mẫu:

* điền placeholder trong biên bản/hợp đồng/mẫu báo cáo
* append một section mới vào đúng vị trí
* merge nội dung mới nhưng giữ numbering/style chain

Metric trọng tâm:

* placeholder fill accuracy
* heading/numbering continuity
* local style conformity

## 15.3 PPTX generation/edit tasks

Task mẫu:

* tạo deck từ outline + số liệu
* sửa deck hiện có mà giữ master/layout
* thêm chart, speaker note, appendix

Metric trọng tâm:

* slide count / section coverage
* overlap rate, overflow rate, off-slide rate
* narrative coherence
* visual hierarchy consistency

## 15.4 XLSX automation tasks

Task mẫu:

* điền công thức, tạo summary sheet, vẽ chart
* giữ nguyên workbook structure nhưng thêm phân tích
* sửa formula/range khi dữ liệu thay đổi

Metric trọng tâm:

* formula correctness
* dependency integrity
* chart/data consistency
* workbook mutation correctness

---

# XVI. Cách đóng gói mỗi benchmark task

Mỗi task trong benchmark nên có một bundle cố định như sau:

```text
task_id/
   instruction.md
   inputs/
      source files...
   template/
      office artifact...
   expected/
      invariants.yaml
      optional reference artifact(s)
      optional judge rubric.md
   evaluator/
      check.py or check.sh
```

Trong đó:

* `instruction.md`: mô tả đúng kiểu user thật sẽ viết
* `inputs/`: markdown, csv, notes, figures, hoặc workbook phụ trợ
* `template/`: file gốc cần preserve scaffold
* `invariants.yaml`: các điều kiện cứng có thể kiểm tự động
* `reference artifact(s)`: 1 hoặc nhiều output chấp nhận được
* `judge rubric.md`: rubric cho LLM-judge hoặc human-judge

Với repo này, `invariants.yaml` nên support ít nhất các trường:

```yaml
mode: preserve-template-scaffold
must_preserve:
   - cover
   - toc
   - section_breaks
   - heading_numbering
must_replace_ranges:
   - chapter_2_body
must_not_contain:
   - "{{"
   - "TODO"
   - duplicated_chapter_heading
format_checks:
   references:
      style_like: template_reference_sample
   toc:
      requires_pageref: true
semantic_checks:
   required_sections:
      - "Kết luận"
      - "Tài liệu tham khảo"
```

---

# XVII. Protocol chấm điểm đề xuất

## 17.1 Mỗi task chạy nhiều lần

Với agentic systems, chạy 1 lần là không đủ. Nên chạy:

* `3` lần cho smoke benchmark
* `5` lần cho result muốn công bố

với seed, temperature và budget được ghi lại rõ ràng.

## 17.2 Báo cáo theo 2 kiểu score

### Hard Success Rate

Chỉ tính pass/fail theo hard gate.

### Weighted Utility Score

Chỉ chấm trên các run qua hard gate:

[
U = 0.35S_{task} + 0.25S_{structure} + 0.20S_{semantic} + 0.10S_{efficiency} + 0.10S_{human}
]

Trong production, hard success rate vẫn là chỉ số quan trọng hơn utility score.

## 17.3 Báo cáo confidence interval

Ít nhất nên có:

* mean
* std
* 95% CI hoặc bootstrap CI

để tránh kết luận từ chênh lệch nhỏ do variance.

## 17.4 Báo cáo theo format và theo task family

Không nên chỉ báo cáo một con số chung cho toàn hệ. Cần tách riêng:

* DOCX preserve/edit
* PPTX generation/edit
* XLSX calculation/manipulation
* cross-file workflow

vì failure mode rất khác nhau.

---

# XVIII. Metrics nên log trong mỗi run

Ngoài artifact cuối, mỗi run nên lưu đầy đủ trajectory để có thể debug và làm ablation.

## 18.1 Trajectory log

Log tối thiểu:

* instruction gốc
* normalized plan
* từng tool call
* tool arguments đã chuẩn hóa hoặc hash
* start/end timestamp
* exit status
* retry count
* error message nếu có
* artifact path của từng intermediate step

## 18.2 Artifact QA log

Nên có file report chuẩn hóa cho từng run:

* package validity
* structure checks
* style checks
* semantic checks
* unresolved residue
* warning/fallback đã kích hoạt

Với repo này, các file như `build_report.json`, `plan.json`, `template_profile.json`, `qa` report nên được xem như source of truth cho evaluation chứ không chỉ là debug output.

## 18.3 Efficiency log

Nên log riêng:

* wall-clock time
* model calls
* token usage
* OfficeCLI calls
* batch/resident reuse ratio
* số lần agent phải re-open file hoặc fallback mode

---

# XIX. Baseline và ablation nên chạy

Muốn chứng minh hệ hiện tại tốt hơn, cần baseline và ablation đủ sắc.

## 19.1 Baseline

Ít nhất nên có 4 baseline:

1. Full regenerate baseline: bỏ template body cũ và sinh lại gần như toàn bộ
2. Direct-edit baseline: chỉnh file trực tiếp nhưng không có scaffold-profile + QA gate
3. Current system: OfficeCLI-native + resident mode + template profile + bounded replacement + QA
4. Human-script baseline: script thủ công deterministic bằng OfficeCLI hoặc API truyền thống

## 19.2 Ablation

Các ablation quan trọng nhất cho repo này:

1. Bỏ template profiling
2. Bỏ preserve-scaffold gate
3. Bỏ post-build QA
4. Không dùng resident/batch mode
5. Không reuse reference-format sample
6. Không rewrite/preserve TOC fields theo strategy hiện tại

Ablation như vậy mới cho thấy improvement đến từ đâu, thay vì chỉ biết final score tăng.

---

# XX. Mapping research source sang hệ này

Nếu cần phần related work ngắn gọn nhưng dùng được ngay, tôi sẽ map như sau:

* **SheetCopilot**: nguồn tham khảo tốt nhất cho XLSX vì có task dataset, nhiều reference solution và execution-based checking trên workbook state.
* **WebArena**: mượn cách viết task ở mức ý định người dùng và cách validator kiểm functional correctness thay vì chỉ chấm text similarity.
* **OSWorld**: mượn cách đóng gói initial state, reproducible environment và trajectory-based evaluation cho workflow thật nhiều bước.
* **AgentBench**: mượn hệ metric cho planning, tool-use, recovery và long-horizon interaction; không dùng làm oracle cho artifact quality.
* **GAIA**: dùng để stress-test reasoning/planning của assistant layer, nhất là task cần tổng hợp nhiều nguồn trước khi sinh tài liệu.
* **DocVQA**: dùng làm sub-benchmark cho năng lực đọc hiểu document/evidence extraction trước khi biên tập tài liệu.
* **ChartQA**: dùng làm sub-benchmark cho chart understanding và reasoning, đặc biệt hữu ích khi chấm PPTX/XLSX chart correctness.

---

# XXI. Bộ metric tối thiểu nên dùng ngay

Nếu cần một bộ metric gọn nhưng đủ mạnh để chạy ngay cho repo này, tôi đề xuất chốt 8 chỉ số chính:

1. **Hard Success Rate**
2. **Requirement Coverage Score**
3. **Structural Integrity Pass Rate**
4. **Formatting Adherence Score**
5. **Semantic Fidelity Score**
6. **Tool Efficiency Score**
7. **Recovery Success Rate**
8. **Human Edit Time**

Trong đó:

* `Hard Success Rate` là KPI số 1 cho production
* `Human Edit Time` là KPI số 1 cho business adoption
* `Structural Integrity Pass Rate` là KPI số 1 cho DOCX/PPTX/XLSX reliability

---

# XXII. Kết luận thực thi

Điểm mấu chốt là: benchmark cho hệ này không nên hỏi đơn giản

> “document cuối có đẹp không?”

mà phải hỏi đúng hơn:

> “agent có hoàn thành task bằng trajectory hợp lý, giữ được scaffold/tính hợp lệ của artifact, và tạo ra output mà con người hầu như không cần sửa thêm hay không?”

Đó là định nghĩa đánh giá sát nhất với một **agentic Office automation system** ở mức research lẫn production.
