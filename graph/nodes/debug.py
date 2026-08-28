
from graph.state import DataAgentState
from graph.chains import debug_chain

def debug_node(state: DataAgentState):    
    human_content = f"""
    - Đoạn code bị lỗi:
    {state.get('code')}
    
    - Lỗi (Exception): {state.get('execution_error')}
    - Traceback: 
    {state.get('traceback')}
    """
    
    response = debug_chain.invoke(
        {"human_message": human_content}
    )
    
    return {
        "debug_feedback": response.content,
    }