import json

from langchain_core.messages import AIMessage, HumanMessage

from graph.nodes.synthetic import synthetic_node
from graph.nodes.validation import validate_node
from graph.state import SyntheticOutput, ValidatorOutput
from graph.tools.visualization import create_chart
from graph.utils import answer_context, format_evidence


def test_context_uses_related_user_messages_and_verified_evidence(tmp_path):
    chart = tmp_path / "chart.png"
    chart.write_bytes(b"png")
    state = {
        "messages": [
            HumanMessage(content="So sánh doanh thu theo vùng"),
            AIMessage(content="Bản nháp chưa xác minh: miền Bắc 999"),
            HumanMessage(content="Vẽ thêm biểu đồ tròn"),
            HumanMessage(content="Nhóm nào lớn nhất?"),
        ],
        "answer_history": [{"question": "Câu trước", "answer": "Đã chấp nhận."}],
        "execution_records": [
            {"status": "error", "step": "Lỗi", "result": {"n": 999}},
            {"status": "success", "step": "Doanh thu theo vùng", "kind": "visualize", "result": {"rows": [{"vùng": "Bắc", "doanh_thu": 60}, {"vùng": "Nam", "doanh_thu": 40}]}, "artifacts": [str(chart)]},
        ],
        "artifacts_dir": str(tmp_path),
        "artifacts": [str(chart), str(chart), str(tmp_path / "missing.png"), str(tmp_path.parent / "outside.png")],
        "profile_summary": "Hai vùng",
        "assumptions": ["Chỉ tính năm 2025"],
    }
    context = answer_context(state)
    assert context["user_question"] == "Nhóm nào lớn nhất?"
    assert context["related_user_messages"] == ["So sánh doanh thu theo vùng", "Vẽ thêm biểu đồ tròn"]
    assert "Đã chấp nhận" in context["conversation_history"]
    assert "Bản nháp" not in str(context)
    evidence = json.loads(context["evidence"])
    assert len(evidence["findings"]) == 1
    assert evidence["findings"][0]["artifact_ids"] == ["ARTIFACT_1"]
    assert evidence["findings"][0]["finding"]["rows"]["rows"][0]["doanh_thu"] == 60
    assert context["artifacts"] == [{"id": "ARTIFACT_1", "path": str(chart), "kind": "image"}]


def test_long_evidence_is_valid_json_with_explicit_omissions():
    rows = [{"group": f"G{i}", "value": i} for i in range(300)]
    rendered = format_evidence([{"status": "success", "step": "Tổng theo nhóm", "kind": "query", "result": {"rows": rows, "returned_rows": 300, "truncated": False}}], max_chars=1800)
    parsed = json.loads(rendered)
    assert len(rendered) <= 1800
    finding = parsed["findings"][0]["finding"]
    assert finding["rows"]["row_count"] == 300
    assert finding["rows"]["omitted_rows"] > 0
    assert finding["rows"]["numeric_summary_of_all_rows"]["value"]["sum"] == 44850
    assert finding["returned_rows"] == 300


def test_pie_chart_returns_plotted_values_and_scope(monkeypatch, tmp_path):
    monkeypatch.setattr("graph.tools.visualization.run_query", lambda *_args, **_kwargs: {
        "rows": [{"group": "A", "value": 60}, {"group": "B", "value": 40}],
        "truncated": False,
    })
    result = create_chart({"artifacts_dir": str(tmp_path)}, "SELECT ...", "pie", x="group", y="value", title="Cơ cấu")
    assert result["chart_data"]["rows"] == [{"group": "A", "value": 60}, {"group": "B", "value": 40}]
    assert result["chart_data"]["numeric_summary_of_all_plotted_rows"]["value"]["sum"] == 100
    assert result["chart_type"] == "pie"
    assert result["source_rows"] == 2
    assert (tmp_path / result["artifacts"][0].split("/")[-1]).is_file()


def test_synthesis_resolves_artifact_codes_into_markdown(monkeypatch, tmp_path):
    chart = tmp_path / "co cau.png"
    chart.write_bytes(b"png")
    export = tmp_path / "ket qua.csv"
    export.write_text("x,y\n1,2\n")

    class FakeChain:
        def invoke(self, payload):
            assert len(payload["artifacts"]) == 2
            return SyntheticOutput(final_answer="Nhóm A chiếm 60%. [[ARTIFACT_1]]\n\nDữ liệu: [[ARTIFACT_2]]")

    monkeypatch.setattr("graph.nodes.synthetic.synthetic_chain", FakeChain())
    result = synthetic_node({"messages": [HumanMessage(content="Cơ cấu?")], "artifacts_dir": str(tmp_path), "artifacts": [str(chart), str(export)]})
    assert f"![Biểu đồ](<{chart}>)" in result["final_answer"]
    assert f"[Tải tệp](<{export}>)" in result["final_answer"]
    assert "[[ARTIFACT_" not in result["final_answer"]


def test_validation_rejects_wrong_artifact_reference_even_if_model_accepts(monkeypatch, tmp_path):
    chart = tmp_path / "chart.png"
    chart.write_bytes(b"png")

    class FakeChain:
        def invoke(self, payload):
            assert payload["related_user_messages"] == ["Vẽ biểu đồ tròn"]
            assert payload["artifacts"][0]["id"] == "ARTIFACT_1"
            return ValidatorOutput(decision="accept")

    monkeypatch.setattr("graph.nodes.validation.validation_chain", FakeChain())
    result = validate_node({
        "messages": [HumanMessage(content="Vẽ biểu đồ tròn"), HumanMessage(content="Giải thích kết quả")],
        "final_answer": "Nhóm A chiếm 60%. ![Biểu đồ](<missing.png>)",
        "artifacts_dir": str(tmp_path),
        "artifacts": [str(chart)],
    })
    assert result["validation_decision"] == "revise_answer"
    assert "answer_history" not in result
    assert "artifact" in result["validation_feedback"]


def test_validation_requires_plotted_values_for_chart_interpretation(monkeypatch, tmp_path):
    chart = tmp_path / "chart.png"
    chart.write_bytes(b"png")

    class FakeChain:
        def invoke(self, payload):
            return ValidatorOutput(decision="accept")

    monkeypatch.setattr("graph.nodes.validation.validation_chain", FakeChain())
    result = validate_node({
        "messages": [HumanMessage(content="Phân tích cơ cấu và kèm biểu đồ tròn")],
        "final_answer": f"A chiếm 60%. ![Biểu đồ](<{chart}>)",
        "artifacts_dir": str(tmp_path),
        "artifacts": [str(chart)],
        "execution_records": [{"status": "success", "kind": "visualize", "result": {"chart_type": "pie", "source_rows": 2}, "artifacts": [str(chart)]}],
    })
    assert result["validation_decision"] == "reanalyze"
    assert "giá trị đã vẽ" in result["validation_feedback"]


def test_validation_requires_requested_chart_artifact(monkeypatch, tmp_path):
    class FakeChain:
        def invoke(self, payload):
            return ValidatorOutput(decision="accept")

    monkeypatch.setattr("graph.nodes.validation.validation_chain", FakeChain())
    result = validate_node({
        "messages": [HumanMessage(content="Vẽ biểu đồ tròn")],
        "final_answer": "Tỷ trọng A là 60%.",
        "artifacts_dir": str(tmp_path),
        "execution_records": [{"status": "success", "kind": "query", "result": {"rows": [{"A": 60}]}}],
    })
    assert result["validation_decision"] == "reanalyze"
