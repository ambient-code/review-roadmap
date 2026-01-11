from typing import Optional

from langchain_core.tools import tool


@tool
def read_file(path: str) -> Optional[str]:
    """
    Reads the full content of ANY file from the repository at the PR's head commit.
    
    This fetches files from the entire codebase, not just files in the PR diff.
    Use this to:
    - Verify that imported modules exist (e.g., fetch 'myproject/utils/helpers.py')
    - Understand parent classes or interfaces referenced by the PR
    - Check helper functions or utilities called by changed code
    - Confirm configuration or constant values referenced in the PR
    
    Args:
        path: Full path to the file from the repository root (e.g., 'src/utils/auth.py')
    
    Returns:
        The file content, or an error message if the file doesn't exist.
    """
    # The actual implementation happens in the node, this is just for schema binding
    return None
