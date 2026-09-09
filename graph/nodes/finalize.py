from langchain_core.messages import AIMessage
from graph.nodes.synthetic import public_artifacts

def finalize_node(state):
    success = (
        state.get("workflow_status") != "failed"
        and (state.get("verification") or {}).get("decision") == "pass"
        and bool(state.get("draft_answer"))
    )
    if success:
        answer = state["draft_answer"]
    else:
        reason = state.get("termination_reason") or state.get("node_error") or "Chưa đủ bằng chứng để xác nhận kết quả."
        answer = f"Phân tích chưa hoàn tất.\n\nLý do: {reason}\n\nĐã chạy thành công {len(state.get('step_results', []))} bước trong kế hoạch hiện tại. Kết quả chưa được xác nhận đầy đủ."
    return {"final_answer": answer, "messages": [AIMessage(content=answer)],
            "workflow_status": "success" if success else "failed",
            "artifacts": public_artifacts(state) if success else []}
