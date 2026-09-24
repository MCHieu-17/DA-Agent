from langchain_core.messages import AIMessage, HumanMessage

from graph.edges.router_after_validation import router_after_validation
from graph.nodes.chat import chat_node
from graph.nodes.cleanup import cleanup_node
from graph.nodes.synthetic import synthetic_node
from graph.nodes.validation import validate_node
from graph.state import SyntheticOutput, ValidatorOutput
from graph.utils import artifact_manifest, format_evidence


def test_evidence_formatter_excludes_failed_records_and_keeps_complete_json():
    rendered = format_evidence([
        {"status": "error", "step": "broken", "error": "ignore this"},
        {"status": "success", "step": "count rooms", "kind": "query", "result": {"rows": [{"count": 3}]}, "artifacts": ["chart.png"]},
        {"status": "success", "step": "chart", "kind": "visualize", "summary": "done", "artifacts": ["chart.png"]},
    ])

    assert "broken" not in rendered
    assert "count rooms" in rendered
    parsed = json.loads(rendered)
    assert len(parsed["findings"]) == 2
    assert parsed["findings"][0]["finding"]["rows"]["rows"][0]["count"] == 3


def test_synthesis_writes_final_answer_without_draft_or_messages(monkeypatch, tmp_path):
    class FakeChain:
        def __init__(self):
            self.payload = None

        def invoke(self, payload):
            self.payload = payload
            return SyntheticOutput(final_answer="Báo cáo đã biên tập.")

    fake_chain = FakeChain()
    monkeypatch.setattr("graph.nodes.synthetic.synthetic_chain", fake_chain)
    chart = tmp_path / "chart.png"
    chart.write_bytes(b"png")
    result = synthetic_node({
        "messages": [HumanMessage(content="Hãy phân tích dữ liệu")],
        "answer_history": [{"question": "Câu trước", "answer": "Trả lời trước"}],
        "past_steps": [{"status": "success", "step": "old", "result": {"n": 0}}],
        "execution_records": [{"status": "success", "step": "Đếm", "result": {"rows": [{"n": 1}]}}],
        "artifacts_dir": str(tmp_path),
        "artifacts": [str(chart), str(chart)],
        "profile_summary": "catalog",
        "assumptions": ["Giả định A"],
    })

    assert result == {"final_answer": "Báo cáo đã biên tập.", "synthesis_retry_count": 0}
    assert "Trả lời trước" in fake_chain.payload["conversation_history"]
    assert "Đếm" in fake_chain.payload["evidence"]
    assert "old" not in fake_chain.payload["evidence"]
    assert fake_chain.payload["artifacts"] == [{"id": "ARTIFACT_1", "path": str(chart), "kind": "image"}]
    assert "draft_answer" not in result
    assert "messages" not in result


def test_synthesis_revision_receives_prior_answer_and_validation_feedback(monkeypatch):
    class FakeChain:
        def __init__(self):
            self.payload = None

        def invoke(self, payload):
            self.payload = payload
            return SyntheticOutput(final_answer="Câu trả lời đã sửa.")

    fake_chain = FakeChain()
    monkeypatch.setattr("graph.nodes.synthetic.synthetic_chain", fake_chain)
    result = synthetic_node({
        "messages": [HumanMessage(content="Phân tích")],
        "final_answer": "Câu trả lời trước.",
        "validation_feedback": "Diễn giải rõ hơn.",
        "synthesis_retry_count": 0,
    })

    assert fake_chain.payload["prior_answer"] == "Câu trả lời trước."
    assert fake_chain.payload["validation_feedback"] == "Diễn giải rõ hơn."
    assert result == {"final_answer": "Câu trả lời đã sửa.", "synthesis_retry_count": 1}


def test_validation_reads_final_answer_and_only_accept_appends_history(monkeypatch):
    class FakeChain:
        def __init__(self):
            self.payload = None

        def invoke(self, payload):
            self.payload = payload
            return ValidatorOutput(decision="accept")

    fake_chain = FakeChain()
    monkeypatch.setattr("graph.nodes.validation.validation_chain", fake_chain)
    result = validate_node({
        "messages": [HumanMessage(content="Phân tích")],
        "final_answer": "Kết quả cuối.",
        "answer_history": [],
        "execution_records": [],
    })

    assert fake_chain.payload["final_answer"] == "Kết quả cuối."
    assert result == {
        "is_sufficient": True,
        "validation_decision": "accept",
        "validation_feedback": None,
        "answer_history": [{"question": "Phân tích", "answer": "Kết quả cuối."}],
    }


def test_validation_exposes_revision_without_saving_history(monkeypatch):
    class FakeChain:
        def invoke(self, payload):
            return ValidatorOutput(decision="revise_answer", feedback="Bổ sung phần diễn giải.")

    monkeypatch.setattr("graph.nodes.validation.validation_chain", FakeChain())
    result = validate_node({"messages": [HumanMessage(content="Phân tích")], "final_answer": "Nháp", "past_steps": []})

    assert result == {
        "is_sufficient": False,
        "validation_decision": "revise_answer",
        "validation_feedback": "Bổ sung phần diễn giải.",
    }
    assert "answer_history" not in result


def test_validation_router_separates_revision_from_reanalysis():
    assert router_after_validation({"validation_decision": "accept"}) == "cleanup"
    assert router_after_validation({"validation_decision": "revise_answer", "synthesis_retry_count": 0, "max_synthesis_retries": 2}) == "synthetic"
    assert router_after_validation({"validation_decision": "reanalyze", "replan_count": 0, "max_replans": 2}) == "planner"
    assert router_after_validation({"validation_decision": "reanalyze", "replan_count": 2, "max_replans": 2}) == "cleanup"


def test_chat_writes_final_answer_directly(monkeypatch):
    class FakeChain:
        def invoke(self, payload):
            return AIMessage(content="Câu trả lời chat.")

    monkeypatch.setattr("graph.nodes.chat.chat_chain", FakeChain())
    result = chat_node({"messages": [HumanMessage(content="Xin chào")]})
    assert result == {"final_answer": "Câu trả lời chat."}


def test_cleanup_closes_sandbox_without_changing_final_answer(monkeypatch):
    cleaned = []
    monkeypatch.setattr("graph.nodes.cleanup.cleanup_sandbox", lambda state: cleaned.append(state["sandbox_id"]))

    result = cleanup_node({"sandbox_id": "sandbox-1", "sandbox_file_map": {"x": "y"}, "final_answer": "Giữ nguyên."})

    assert cleaned == ["sandbox-1"]
    assert result == {"sandbox_id": None, "sandbox_file_map": {}}
    assert "final_answer" not in result


def test_cleanup_is_noop_without_sandbox(monkeypatch):
    def unexpected_cleanup(_state):
        raise AssertionError("cleanup should not be called")

    monkeypatch.setattr("graph.nodes.cleanup.cleanup_sandbox", unexpected_cleanup)
    assert cleanup_node({"sandbox_id": None, "final_answer": "Giữ nguyên."}) == {}


def test_graph_has_no_finalizer_and_public_output_only_exposes_final_answer():
    from graph.graph import app

    assert "finalize_answer" not in app.get_graph().nodes
    assert set(app.get_output_jsonschema()["properties"]) == {"final_answer"}
import json
