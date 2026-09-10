MEMORY_UPDATE_PROMPT = """
You are maintaining long-term conversation memory.

Existing memory summary:

{existing_summary}

Update the memory using the important information from
the conversation.

Keep:

- User preferences
- User goals
- Important decisions
- Ongoing tasks
- Technical details
- Important facts
- Important conclusions

Do NOT store:

- Small talk
- Repeated information
- Raw tool output
- Large retrieved document chunks
- Unnecessary details

Return only the updated memory summary.
"""

MEMORY_INITIAL_PROMPT = """
Create a concise long-term memory summary of this conversation.

Keep:

- User preferences
- User goals
- Important decisions
- Ongoing tasks
- Technical details
- Important facts
- Important conclusions

Do NOT store:

- Small talk
- Repeated information
- Raw tool output
- Large retrieved document chunks
- Unnecessary details

Return only the memory summary.
"""