"""Manual, paired prompt evaluation on the configured model.

Run: python scripts/evaluate_synthesis_prompts.py
Inspect the printed answers for factual coverage and Vietnamese prose quality.
No uploaded files or private data are sent by this script.
"""

from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate

from graph.llms import llm
from graph.prompts.synthetic_prompt import synthetic_prompt
from graph.settings import settings
from graph.state import SyntheticOutput


BASELINE = ChatPromptTemplate.from_messages([
    ("system", """You write the complete final data-analysis answer in the user's language. Use only supplied evidence; never invent figures or conclusions.
Lead with a direct conclusion. Present the key figures and comparisons, and explain what they mean. Organize the answer naturally around every requested deliverable. Do not narrate nodes, tools, code, or raw execution results, and do not use mechanical phrases such as saying that an image or chart was created successfully. Mention an artifact only when it helps answer the request, using the supplied path exactly. State assumptions and limitations when they materially affect the conclusion. Keep every claim proportional to the evidence.
If a prior answer and reviewer feedback are supplied, rewrite the entire answer to resolve the feedback instead of appending a revision note or discussing the review process."""),
    ("human", """Current question: {user_question}

Accepted conversation context:
{conversation_history}

Data catalog:
{profile_summary}

Assumptions:
{assumptions}

Verified execution evidence (JSON):
{evidence}

Available artifacts:
{artifacts}

Prior answer:
{prior_answer}

Reviewer feedback:
{validation_feedback}"""),
])


CASES = [
    {
        "name": "short",
        "question": "Có bao nhiêu đơn hàng?",
        "evidence": [{"objective": "Đếm đơn hàng", "kind": "query", "finding": {"rows": [{"orders": 125}]}}],
        "must_include": ["125"],
    },
    {
        "name": "multi_part",
        "question": "So sánh doanh thu Bắc và Nam, nêu tỷ trọng và kết luận.",
        "evidence": [{"objective": "Doanh thu theo vùng", "kind": "query", "finding": {"rows": [{"region": "Bắc", "revenue": 60, "share_pct": 60}, {"region": "Nam", "revenue": 40, "share_pct": 40}], "unit": "tỷ đồng"}}],
        "must_include": ["60", "40", "Bắc", "Nam"],
    },
    {
        "name": "pie_chart",
        "question": "Phân tích cơ cấu doanh thu và kèm biểu đồ tròn.",
        "evidence": [{"objective": "Cơ cấu doanh thu", "kind": "visualize", "finding": {"chart_type": "pie", "chart_data": {"rows": [{"region": "Bắc", "revenue": 60}, {"region": "Nam", "revenue": 40}], "numeric_summary_of_all_plotted_rows": {"revenue": {"sum": 100}}}}, "artifact_ids": ["ARTIFACT_1"]}],
        "artifacts": [{"id": "ARTIFACT_1", "path": "/tmp/pie_chart.png", "kind": "image"}],
        "must_include": ["60", "40"],
    },
    {
        "name": "follow_up",
        "question": "Vậy khu vực nào dẫn đầu và hơn bao nhiêu?",
        "related": ["Hãy so sánh doanh thu theo khu vực."],
        "history": "User: So sánh Bắc và Nam.\nAI: Bắc 60 tỷ đồng, Nam 40 tỷ đồng.",
        "evidence": [{"objective": "Chênh lệch doanh thu", "kind": "query", "finding": {"rows": [{"leader": "Bắc", "difference": 20, "unit": "tỷ đồng"}]}}],
        "must_include": ["Bắc", "20"],
    },
    {
        "name": "missing_data",
        "question": "Doanh thu năm 2024 tăng bao nhiêu phần trăm so với 2023?",
        "evidence": [{"objective": "Kiểm tra năm dữ liệu", "kind": "query", "finding": {"rows": [{"year": 2024, "revenue": 90}], "no_2023_data": True}}],
        "must_include": ["2023"],
    },
]


def main() -> None:
    model = llm.with_structured_output(SyntheticOutput)
    print(f"Model: {settings.llm_provider}/{settings.llm_model}; temperature={settings.llm_temperature}")
    for case in CASES:
        base = {
            "user_question": case["question"],
            "conversation_history": case.get("history", "(bắt đầu hội thoại)"),
            "profile_summary": "Bảng doanh thu theo vùng và năm.",
            "assumptions": [],
            "evidence": json.dumps({"findings": case["evidence"]}, ensure_ascii=False),
            "artifacts": case.get("artifacts", []),
            "prior_answer": "",
            "validation_feedback": "",
        }
        for label, prompt, payload in (
            ("baseline", BASELINE, base),
            ("proposed", synthetic_prompt, {**base, "related_user_messages": case.get("related", [])}),
        ):
            try:
                answer = (prompt | model).invoke(payload).final_answer
                missing = [term for term in case["must_include"] if term not in answer]
                print(json.dumps({"case": case["name"], "prompt": label, "missing_terms": missing, "answer": answer}, ensure_ascii=False))
            except Exception as exc:
                print(json.dumps({"case": case["name"], "prompt": label, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
