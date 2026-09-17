from pydantic import BaseModel


class HITLResumeRequest(BaseModel):
    thread_id: str
    decision: str