from __future__ import annotations

from langgraph.graph import END, StateGraph

from agentsystem.agents.backend_dev_agent import backend_dev_node
from agentsystem.agents.database_agent import database_dev_node
from agentsystem.agents.devops_agent import devops_dev_node
from agentsystem.agents.doc_agent import doc_node
from agentsystem.agents.fix_agent import fix_node
from agentsystem.agents.frontend_dev_agent import frontend_dev_node
from agentsystem.agents.requirement_agent import requirement_analysis_node
from agentsystem.agents.router_agent import route_after_test, task_router
from agentsystem.agents.review_agent import review_node
from agentsystem.agents.security_agent import security_node
from agentsystem.agents.sync_agent import sync_merge_node
from agentsystem.agents.test_agent import test_node
from agentsystem.agents.workspace_prep_agent import workspace_prep_node
from agentsystem.core.state import DevState


def create_dev_graph():
    workflow = StateGraph(DevState)
    workflow.add_node("requirement_analysis", requirement_analysis_node)
    workflow.add_node("workspace_prep", workspace_prep_node)
    workflow.add_node("backend_dev", backend_dev_node)
    workflow.add_node("frontend_dev", frontend_dev_node)
    workflow.add_node("database_dev", database_dev_node)
    workflow.add_node("devops_dev", devops_dev_node)
    workflow.add_node("sync_merge", sync_merge_node)
    workflow.add_node("tester", test_node)
    workflow.add_node("fixer", fix_node)
    workflow.add_node("security_scanner", security_node)
    workflow.add_node("reviewer", review_node)
    workflow.add_node("doc_writer", doc_node)
    workflow.set_entry_point("requirement_analysis")
    workflow.add_edge("requirement_analysis", "workspace_prep")
    workflow.add_conditional_edges(
        "workspace_prep",
        task_router,
        {
            "backend_dev": "backend_dev",
            "frontend_dev": "frontend_dev",
            "database_dev": "database_dev",
            "devops_dev": "devops_dev",
            "sync_merge": "sync_merge",
        },
    )
    workflow.add_edge("backend_dev", "sync_merge")
    workflow.add_edge("frontend_dev", "sync_merge")
    workflow.add_edge("database_dev", "sync_merge")
    workflow.add_edge("devops_dev", "sync_merge")
    workflow.add_edge("sync_merge", "tester")
    workflow.add_conditional_edges(
        "tester",
        route_after_test,
        {
            "fixer": "fixer",
            "security_scanner": "security_scanner",
        },
    )
    workflow.add_edge("fixer", "tester")
    workflow.add_edge("security_scanner", "reviewer")
    workflow.add_edge("reviewer", "doc_writer")
    workflow.add_edge("doc_writer", END)
    return workflow.compile()
