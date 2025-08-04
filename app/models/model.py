from pydantic import BaseModel
from typing import List, Optional

class requestFormData(BaseModel):
    name: str
    email: str
    password: str

class responseFormData(BaseModel):
    name: str
    email: str
    text: str

class Base(BaseModel):

    qst:str
    ans:str

class QnA(BaseModel):
    # sid:int
    inputs:list[Base]   

# for question generation
class QuestionRequest(BaseModel):
    role: str
    skills: List[str]
    experience: Optional[int] = 0    