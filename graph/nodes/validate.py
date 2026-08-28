from graph.state import DataAgentState

def validator_node(state: DataAgentState):
    user_question = state["messages"][-1].content
    past_steps = state.get("past_steps", [])