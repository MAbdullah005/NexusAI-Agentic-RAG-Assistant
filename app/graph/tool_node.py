from app.tools.python_executor import python_executor
from app.tools.calculator_tool import calculator
from app.tools.unified_rag_tool import unified_rag_tool
from app.tools.search_tool import search_tool
from app.tools.stock_tool import get_stock_price
from app.llm.llm_config import llm
from langgraph.prebuilt import ToolNode

tools = [
    search_tool,
    get_stock_price,
    calculator,
    unified_rag_tool,
    python_executor,
]



llm_with_tools = llm.bind_tools(tools)


tool_node = ToolNode(tools)