from __future__ import annotations

from app.graph.state import ChatState
from langchain_core.messages import AIMessage


def not_found_answer_node(state: ChatState):

    return {
        "messages": [
            AIMessage(
                content=(
                    "I couldn't find information answering "
                    "your question in the uploaded documents."
                )
            )
        ]
    }