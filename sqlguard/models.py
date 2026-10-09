from pydantic import BaseModel, Field
class Generated(BaseModel):
    sql: str
    explanation: str
    confidence: float=Field(ge=0,le=1)
    tables: list[str]=[]
    columns: list[str]=[]
class Judgment(BaseModel):
    reconstructed_question: str
    alignment: float=Field(ge=0,le=1)
    reason: str
class Query(BaseModel):
    question: str=Field(min_length=3,max_length=2000)
    session_id: str=Field(default="local",pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    sql_override: str | None=Field(default=None,max_length=10000)
    validate_alternative: bool=False
class Feedback(BaseModel):
    query_id: str
    session_id: str="local"
    correct: bool
