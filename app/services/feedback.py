import os
import json
import sqlite3
from typing import Any, Dict, List

from dotenv import load_dotenv
import google.generativeai as genai


load_dotenv()


# SQLite configuration (reuse the same DB file as other services)
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "app/includes/site.db")


# Gemini configuration (prefer env key; falls back to whatever may already be set elsewhere)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def fetch_qna_for_session(session_id: str) -> List[Dict[str, Any]]:
    """Fetch interview QnA rows for a given session from SQLite."""
    connection = sqlite3.connect(SQLITE_DB_PATH)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT question, answer FROM users WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        )
        rows = cursor.fetchall()
    finally:
        connection.close()

    return [
        {"question": (row[0] or ""), "answer": (row[1] or "")}
        for row in rows
    ]


def _build_qna_text(qnas: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    for idx, qa in enumerate(qnas, start=1):
        question = (qa.get("question") or "").strip()
        answer = (qa.get("answer") or "").strip()
        lines.append(f"Q{idx}: {question}")
        lines.append(f"A{idx}: {answer}")
    return "\n".join(lines)


def _basic_heuristic_feedback(qnas: List[Dict[str, str]]) -> Dict[str, Any]:
    """Fallback feedback when LLM key is unavailable: simple completeness score."""
    total_questions = len(qnas)
    answered = sum(1 for qa in qnas if (qa.get("answer") or "").strip())
    completeness = int((answered / max(total_questions, 1)) * 100)
    strengths: List[str] = []
    improvements: List[str] = []

    if answered:
        strengths.append(f"Answered {answered} of {total_questions} questions")
    if answered < total_questions:
        improvements.append("Provide answers to all questions to improve completeness")

    return {
        "score": completeness,
        "summary": "Basic completeness-based feedback (LLM not configured).",
        "strengths": strengths,
        "improvements": improvements,
        "suggestions": [
            "Review unanswered questions and prepare concise, structured responses",
            "Use the STAR method (Situation, Task, Action, Result) for behavioral answers",
        ],
    }


def generate_feedback_for_session(session_id: str) -> Dict[str, Any]:
    """Generate actionable interview feedback for a given session.

    - Pulls QnA from MongoDB using the configured URI/DB/collection
    - If GEMINI_API_KEY is present, uses Gemini to produce detailed feedback
    - Otherwise, returns a basic heuristic-based feedback
    """
    qnas = fetch_qna_for_session(session_id)
    if not qnas:
        return {
            "session_id": session_id,
            "score": None,
            "summary": "No Q&A found for the provided session.",
            "strengths": [],
            "improvements": [],
            "suggestions": [],
        }

    if not GEMINI_API_KEY:
        basic = _basic_heuristic_feedback(qnas)
        return {"session_id": session_id, **basic}

    qna_text = _build_qna_text(qnas)

    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
You are an expert Interview Coach. Review the following interview questions and the candidate's answers. Provide concise, actionable feedback.

Return a strict JSON object with the following keys (and no extra text):
- score: integer 0-100
- summary: short paragraph
- strengths: string array
- improvements: string array
- suggestions: string array (targeted practice or resources)

Interview Q&A:
{qna_text}
"""

    response = model.generate_content(prompt)
    text = getattr(response, "text", "") or ""
    cleaned = text.strip()

    # Strip possible code fences
    if cleaned.startswith("```"):
        # remove leading and trailing backticks blocks
        cleaned = cleaned.strip("`")
        # find first JSON object
        brace_index = cleaned.find("{")
        if brace_index != -1:
            cleaned = cleaned[brace_index:]

    try:
        data = json.loads(cleaned)
    except Exception:
        data = {
            "score": None,
            "summary": text or "Feedback generation failed to produce valid JSON.",
            "strengths": [],
            "improvements": [],
            "suggestions": [],
        }

    return {"session_id": session_id, **data}
