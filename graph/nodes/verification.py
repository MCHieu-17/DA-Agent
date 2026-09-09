import json
import configuration as cfg
from graph.llms import get_node_llm
from graph.prompts import verification_prompt
from graph.state import VerificationResult
from graph.runtime import read_result
from graph.recovery import fail, model_failure, request_replan
from graph.nodes.synthetic import public_artifacts
from graph.utils import analysis_context

def verification_node(state):
    # Deterministic evidence checks precede the semantic judge.
    try:
        steps, results = state["plan"]["steps"], state["step_results"]
        if len(steps) != len(results) or state["current_step_index"] != len(steps):
            raise ValueError("Not all steps completed.")
        for step, result in zip(steps, results):
            if result["plan_version"] != state["plan_version"] or result["step"] != step["step"]:
                raise ValueError("Stale step evidence.")
            from graph.integrity import verify_files
            verify_files(result)
    except Exception as exc:
        return request_replan(state, f"Evidence contract failed: {exc}")
    try:
        result = (verification_prompt | get_node_llm("verification").with_structured_output(VerificationResult)).invoke({
            **analysis_context(state), "draft_answer": state["draft_answer"],
            "artifacts": json.dumps(public_artifacts(state), ensure_ascii=False),
        })
        allowed = {r["ref"] for r in results}
        if any(ref not in allowed for check in result.checks for ref in check.evidence_refs):
            raise ValueError("Verification referenced unavailable evidence.")
    except Exception as exc:
        return model_failure("Verification", exc)
    update = {"verification": result.model_dump()}
    if result.decision == "replan":
        update.update(request_replan(state, result.feedback))
    elif result.decision == "clarify":
        update["clarification_question"] = result.clarification_question
    elif result.decision == "revise_answer" and state["answer_revision_count"] >= cfg.MAX_ANSWER_REVISIONS:
        update.update(fail(f"Answer revision budget exhausted. {result.feedback}"))
    return update
