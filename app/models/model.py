from pydantic import BaseModel

class requestFormData(BaseModel):
    name: str
    email: str
    password: str

class responseFormData(BaseModel):
    name: str
    email: str
    text: str