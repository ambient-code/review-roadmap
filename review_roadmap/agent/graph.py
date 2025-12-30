from langgraph.graph import StateGraph, END
from review_roadmap.agent.state import ReviewState
from review_roadmap.agent.nodes import analyze_structure, context_expansion, draft_roadmap

def build_graph():
    workflow = StateGraph(ReviewState)
    
    # Add Nodes
    workflow.add_node("analyze_structure", analyze_structure)
    workflow.add_node("context_expansion", context_expansion)
    workflow.add_node("draft_roadmap", draft_roadmap)
    
    # Define Edges
    workflow.set_entry_point("analyze_structure")
    workflow.add_edge("analyze_structure", "context_expansion")
    workflow.add_edge("context_expansion", "draft_roadmap")
    workflow.add_edge("draft_roadmap", END)
    
    return workflow.compile()
