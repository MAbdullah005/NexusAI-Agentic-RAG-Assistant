from typing import Optional
from pydantic import BaseModel


class HITLResumeRequest(BaseModel):
    thread_id: str
    decision: str
    message_id: Optional[str] = None