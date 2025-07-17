from fastapi import APIRouter, Form
from app.models.model import requestFormData, responseFormData

router = APIRouter()

@router.get("/")
def root():
    return {"message":"hello from server"}

