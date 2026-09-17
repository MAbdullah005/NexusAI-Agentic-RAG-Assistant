from __future__ import annotations

from typing import (
    Annotated,
    Any,
    Dict,
    List,
    TypedDict,
)

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatState(TypedDict, total=False):

    messages: Annotated[
        List[BaseMessage],
        add_messages
    ]

    tool_call: Dict[str, Any]

    summary: str

    rag_grade: str

    hitl_decision : str

    answer_source: str