from pydantic import BaseModel

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