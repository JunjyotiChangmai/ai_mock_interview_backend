from fastapi import APIRouter, Form
from app.models.model import requestFormData, responseFormData,QnA
from app.services import db

router = APIRouter()

db.init_db()

@router.get("/")
def root():
    return {"message":"hello from server"}

@router.post("/name")
def name(student:QnA):
    for qu in student.inputs:
        db.ins_inp(qu.qst,qu.ans)
    # here id may be needed without auto increment by manually configuring

    return {"message": "Thanks for using this"}

# only for testing database
@router.get("/test")
def test():
    return db.view()