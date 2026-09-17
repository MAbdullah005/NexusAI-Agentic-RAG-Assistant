from __future__ import annotations

import json

from app.graph.state import ChatState
from app.tools.search_tool import search_tool
from langchain_core.messages import ToolMessage


def web_search_node(state: ChatState):

    messages = state.get(
        "messages",
        []
    )

    user_question = None

    # --------------------------------------------------------
    # Get original user question
    # --------------------------------------------------------

    for message in reversed(messages):

        if getattr(
            message,
            "type",
            None
        ) == "human":

            user_question = message.content
            break

    if not user_question:

        return {
            "messages": []
        }

    print("\n" + "=" * 80)
    print("[WEB SEARCH NODE]")
    print("=" * 80)

    print(
        f"[WEB SEARCH] Query: {user_question}"
    )

    # --------------------------------------------------------
    # Run web search
    # --------------------------------------------------------

    result = search_tool.invoke(
        {
            "query": user_question
        }
    )

    print(
        "[WEB SEARCH] Search completed"
    )

    print(
        f"[WEB SEARCH] Result type: {type(result)}"
    )

    print(
        f"[WEB SEARCH] Number of results: "
        f"{len(result) if isinstance(result, list) else 'N/A'}"
    )

    # --------------------------------------------------------
    # Convert search results to a valid LangChain message
    # --------------------------------------------------------

    if isinstance(result, list):

        search_content = json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )

    else:

        search_content = str(result)

    web_message = ToolMessage(
        content=search_content,
        name="web_search",
        tool_call_id="hitl_web_search"
    )

    print(
        "[WEB SEARCH] Search results converted to ToolMessage"
    )

    print("\n \n \n \n Here is the web serach data last wrods ",web_message,"\n /n \n /n")

    return {
        "messages": [web_message],
        "answer_source": "web"
    }