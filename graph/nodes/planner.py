from pydantic import ValidationError
from langchain_core.exceptions import OutputParserException
from graph.llms import get_node_llm
from graph.prompts import planner_prompt
from graph.state import AnalysisPlan
from graph.recovery import model_failure, request_replan
from graph.utils import analysis_context

def check_plan(plan, profiles):
    available = {p["dataset_id"]: [c["name"] for c in p["columns"]] for p in profiles}
    kinds = {key: "table" for key in available}
    for index, step in enumerate(plan["steps"], 1):
        postgres = {p["dataset_id"] for p in profiles if p.get("kind") == "postgres"}
        used = {i["source"] for i in step["inputs"]}
        if step.get("engine", "python") == "postgres_sql":
            if not used <= postgres or step["expected_output"]["type"] == "chart":
                raise ValueError("PostgreSQL steps require database inputs and scalar/table output.")
        elif used & postgres:
            raise ValueError("Extract PostgreSQL inputs using a postgres_sql step first.")
        if step["step"] != index:
            raise ValueError("Step numbers must be consecutive from 1.")
        sources = [i["source"] for i in step["inputs"]]
        if len(set(sources)) != len(sources):
            raise ValueError("Declare each source once, listing all required columns.")
        for item in step["inputs"]:
            source = item["source"]
            if source not in available or kinds[source] == "chart":
                raise ValueError(f"Unknown, future, or chart input: {source}")
            missing = set(item["columns"]) - set(available[source])
            if missing:
                raise ValueError(f"{source}: unknown columns {sorted(missing)}")
        output = step["expected_output"]
        unknown = set(output.get("non_null_columns", []) + output.get("unique_columns", [])) - set(output["columns"])
        if unknown:
            raise ValueError(f"Step {index}: output assertions reference {sorted(unknown)}, but output columns are {output['columns']}. Use only OUTPUT table column names; scalar/chart require empty assertion lists.")
        if output["type"] != "table" and output.get("row_count") is not None:
            raise ValueError(f"Step {index}: row_count is a table assertion; set it to null for scalar/chart output.")
        if output["type"] == "table" and (
            not output["columns"] or len(set(output["columns"])) != len(output["columns"])
        ):
            raise ValueError("Table output requires unique named columns.")
        if output["type"] != "table" and output["columns"]:
            raise ValueError("Only table outputs have columns.")
        available[f"step_{index}"] = output["columns"]
        kinds[f"step_{index}"] = output["type"]

def planner_node(state):
    update = {}
    if state.get("replan_reason"):
        history = [*state.get("plan_history", []), {
            "plan_version": state["plan_version"], "plan": state.get("plan", {}),
            "step_results": state.get("step_results", []),
            "reason": state["replan_reason"], "verification": state.get("verification"),
        }]
        update.update(replan_count=state["replan_count"] + 1, plan_version=state["plan_version"] + 1,
                      plan_history=history, plan={}, step_results=[], current_step_index=0,
                      code=None, debug_count=0, answer_revision_count=0, verification=None,
                      draft_answer=None)
    effective = {**state, **update}
    try:
        result = (planner_prompt | get_node_llm("planner").with_structured_output(AnalysisPlan)).invoke(analysis_context(state, "planner"))
        plan = result.model_dump()
        if result.clarification_question:
            return {**update, "clarification_question": result.clarification_question}
    except (ValidationError, OutputParserException) as exc:
        return {**update, **request_replan(effective, f"Invalid plan: {exc}")}
    except Exception as exc:
        return {**update, **model_failure("Planner", exc)}
    try:
        check_plan(plan, state["profiles"])
    except ValueError as exc:
        return {**update, **request_replan(effective, f"Invalid plan: {exc}")}
    return {
        **update, "plan": plan, "step_results": [], "current_step_index": 0, "code": None,
        "debug_count": 0, "answer_revision_count": 0, "verification": None,
        "draft_answer": None, "replan_reason": None, "execution_status": None,
        "execution_error": None, "execution_output": None, "traceback": None, "node_error": None,
    }
