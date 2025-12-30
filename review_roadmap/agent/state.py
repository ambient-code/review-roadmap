from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from review_roadmap.models import PRContext

class ReviewState(BaseModel):
    """The state of the review agent."""
    
    # Input
    pr_context: PRContext
    
    # Intermediate Reasoning
    topology: Dict[str, Any] = Field(default_factory=dict, description="Grouped files logic")
    required_context: List[str] = Field(default_factory=list, description="List of file paths to fetch content for")
    fetched_content: Dict[str, str] = Field(default_factory=dict, description="Content of fetched files")
    
    # Output
    roadmap: str = ""
