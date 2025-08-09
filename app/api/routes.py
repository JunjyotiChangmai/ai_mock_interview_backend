from fastapi import APIRouter, Form
import uuid
from app.models.model import requestFormData, responseFormData,QnA,QuestionRequest
from app.services.question_generator import generate_questions
from app.services.feedback import generate_feedback_for_session
from app.services import db

router = APIRouter()

db.init_db()

@router.get("/")
def root():
    return {"message":"hello from server"}

@router.post("/name")
def name(student: QnA):
    session_id = student.session_id or str(uuid.uuid4())
    for qu in student.inputs:
        db.ins_inp(qu.qst, qu.ans, session_id=session_id)
    return {"message": "Thanks for using this", "session_id": session_id}

# only for testing database
@router.get("/test")
def test():
    return db.view()

# question generator api (working)
@router.post("/generate-questions")
async def generate(request: QuestionRequest):
    questions = generate_questions(
        role=request.role,
        skills=request.skills,
        experience=request.experience
    )
    return {"questions": questions}


# feedback generation from MongoDB Q&A
@router.get("/feedback/{session_id}")
async def feedback(session_id: str):
    return generate_feedback_for_session(session_id)