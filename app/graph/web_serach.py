from __future__ import annotations

from app.graph.state import ChatState
from app.tools.search_tool import search_tool

from langchain_core.messages import AIMessage


def web_search_node(state: ChatState):

    messages = state.get(
        "messages",
        []
    )

    # ========================================================
    # GET ORIGINAL USER QUESTION
    # ========================================================

    user_question = None

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
            "messages": [
                AIMessage(
                    content=(
                        "I couldn't determine the user's question."
                    )
                )
            ],
            "answer_source": "web"
        }

    print("\n" + "=" * 80)
    print("[WEB SEARCH NODE]")
    print("=" * 80)

    print(
        f"[WEB SEARCH] Original question: {user_question}"
    )

    # ========================================================
    # BUILD SEARCH QUERY
    # ========================================================

    web_query = build_web_query(
        user_question
    )

    print(
        f"[WEB SEARCH] Search query: {web_query}"
    )

    # ========================================================
    # SEARCH WEB
    # ========================================================

    results = search_tool.invoke(
        {
            "query": web_query
        }
    )

    print(
        "[WEB SEARCH] Search completed"
    )

    print(
        f"[WEB SEARCH] Result type: {type(results)}"
    )

    # ========================================================
    # NO RESULTS
    # ========================================================

    if not results:

        return {
            "messages": [
                AIMessage(
                    content=(
                        "I couldn't find relevant information "
                        "from the web."
                    )
                )
            ],
            "answer_source": "web"
        }

    # ========================================================
    # FORMAT WEB RESULTS DIRECTLY
    # ========================================================

    response_parts = []

    response_parts.append(
        f"🌐 **Web search results for:** `{web_query}`\n"
    )

    for index, result in enumerate(
        results[:5],
        start=1
    ):

        title = result.get(
            "title",
            "Untitled"
        )

        url = result.get(
            "url",
            ""
        )

        content = result.get(
            "content",
            ""
        )

        score = result.get(
            "score"
        )

        response_parts.append(
            f"""
### {index}. {title}

{content}

🔗 {url}
"""
        )

    final_web_response = "\n".join(
        response_parts
    )

    print(
        "[WEB SEARCH] Direct web response prepared"
    )

    # ========================================================
    # RETURN DIRECTLY TO USER
    # ========================================================

    return {
        "messages": [
            AIMessage(
                content=final_web_response
            )
        ],
        "answer_source": "web"
    }


def build_web_query(
    question: str
) -> str:

    query = question.strip()

    phrases_to_remove = [
        "i have given you pdf",
        "i have give you pdf",
        "i have given you a pdf",
        "i have give you a pdf",
        "from this pdf",
        "from the pdf",
        "from this document",
        "from the document",
        "from this",
    ]

    for phrase in phrases_to_remove:

        query = query.replace(
            phrase,
            ""
        )

    query = " ".join(
        query.split()
    )

    return query