import json
from graph.llms import get_node_llm
from graph.prompts import synthetic_prompt
from graph.state import SyntheticOutput
from graph.recovery import model_failure
from graph.utils import analysis_context

def public_artifacts(state):
    return sorted({p for r in state.get("step_results", []) for p in r.get("artifacts", [])})

def synthetic_node(state):
    revisions = state["answer_revision_count"] + int(
        (state.get("verification") or {}).get("decision") == "revise_answer")
    try:
        result = (synthetic_prompt | get_node_llm("synthetic").with_structured_output(SyntheticOutput)).invoke({
            **analysis_context(state, "synthetic"), "draft_answer": state.get("draft_answer") or "",
            "artifacts": json.dumps(public_artifacts(state), ensure_ascii=False),
        })
        return {"draft_answer": result.final_answer, "answer_revision_count": revisions}
    except Exception as exc:
        return model_failure("Synthetic", exc)
