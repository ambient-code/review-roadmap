from typing import Optional

from langchain_core.tools import tool


@tool
def read_file(path: str) -> Optional[str]:
    """
    Reads the full content of a specific file from the PR.
    Use this when you need to see the code context surrounding a change,
    or to understand a whole class/module definition.
    """
    # The actual implementation happens in the node, this is just for schema binding
    return None
