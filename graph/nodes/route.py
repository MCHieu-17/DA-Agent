from graph.state import DataAgentState, RouteDecision
from graph.chains import llm_router_chain

def route_node(state: DataAgentState):
    decision: RouteDecision = llm_router_chain.invoke(
        {
            "user_question": state["messages"][-1].content,
            "schema_str": state["schema_str"]
        }
    )
    return {"intent": decision.intent}


