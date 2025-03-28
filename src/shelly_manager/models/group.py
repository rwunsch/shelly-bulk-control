from typing import List, Optional
from pydantic import BaseModel, Field

class Group(BaseModel):
    id: str = Field(..., description="Unique group identifier")
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    device_ids: List[str] = Field(default_factory=list, description="List of device IDs in this group")
    parent_group_id: Optional[str] = Field(None, description="ID of parent group if nested")
    metadata: dict = Field(default_factory=dict, description="Additional group metadata") 