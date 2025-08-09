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


_STOPWORDS = {
    "the","a","an","and","or","but","if","then","else","for","to","of","in","on","at","by",
    "is","are","was","were","be","been","being","with","as","that","this","it","its","from","into",
}


def _tokenize(text: str) -> List[str]:
    return [w.strip(".,:;!?()[]{}\"'`).-_").lower() for w in text.split()]  # simple tokenizer


def _keywords_from_question(question: str) -> List[str]:
    tokens = _tokenize(question)
    return [t for t in tokens if len(t) >= 4 and t not in _STOPWORDS]


def _keyword_coverage_score(keywords: List[str], answer: str) -> float:
    if not keywords:
        return 1.0
    answer_tokens = set(_tokenize(answer))
    hits = sum(1 for k in set(keywords) if k in answer_tokens)
    return hits / len(set(keywords))


def _length_score(answer: str) -> float:
    # Prefer 40-180 words window
    words = [t for t in _tokenize(answer) if t]
    n = len(words)
    if n == 0:
        return 0.0
    if 40 <= n <= 180:
        return 1.0
    # decay if too short/long
    if n < 40:
        return max(0.0, n / 40.0)
    return max(0.0, 1.0 - (n - 180) / 220.0)


def _clarity_score(answer: str) -> float:
    # Simple heuristic: more sentences and fewer filler words are better
    sentences = [s for s in answer.replace("?", ".").replace("!", ".").split(".") if s.strip()]
    num_sentences = len(sentences)
    fillers = ["basically", "like", "sort of", "kind of", "actually", "literally"]
    filler_hits = sum(answer.lower().count(f) for f in fillers)
    if num_sentences == 0:
        return 0.0
    base = min(1.0, num_sentences / 4.0)
    penalty = min(0.4, filler_hits * 0.05)
    return max(0.0, base - penalty)


def _structure_score(answer: str) -> float:
    # Detect STAR-like structure
    lower = answer.lower()
    hits = sum(1 for k in ["situation", "task", "action", "result", "impact", "learned"] if k in lower)
    return min(1.0, hits / 4.0)


def _technical_depth_score(answer: str, keywords: List[str]) -> float:
    lower = answer.lower()
    code_markers = ["def ", "class ", "{", "}", "=>", "<>", "try:", "catch", "finally", "SELECT ", "JOIN "]
    marker_hits = sum(1 for m in code_markers if m.lower() in lower)
    numbers = sum(c.isdigit() for c in lower)
    keyword_hits = sum(1 for k in set(keywords) if k in lower)
    score = 0.0
    score += min(0.4, marker_hits * 0.1)
    score += min(0.2, (numbers > 0) * 0.2)
    score += min(0.4, keyword_hits * 0.08)
    return min(1.0, score)


def _build_per_question_feedback(qnas: List[Dict[str, str]]) -> Dict[str, Any]:
    items = []
    strengths: List[str] = []
    improvements: List[str] = []
    total_scores: List[float] = []

    for idx, qa in enumerate(qnas, start=1):
        q = (qa.get("question") or "").strip()
        a = (qa.get("answer") or "").strip()
        kwords = _keywords_from_question(q)
        kw_cov = _keyword_coverage_score(kwords, a)
        len_s = _length_score(a)
        clr_s = _clarity_score(a)
        str_s = _structure_score(a)
        tech_s = _technical_depth_score(a, kwords)

        # weight: coverage 0.35, length 0.15, clarity 0.15, structure 0.15, technical 0.20
        q_score = (
            0.35 * kw_cov + 0.15 * len_s + 0.15 * clr_s + 0.15 * str_s + 0.20 * tech_s
        )
        total_scores.append(q_score)

        q_strengths = []
        q_impr = []
        if kw_cov >= 0.7:
            q_strengths.append("Addresses most key concepts in the question")
        else:
            q_impr.append("Cover more of the question's key terms and concepts")
        if len_s >= 0.8:
            q_strengths.append("Good level of detail and elaboration")
        elif len_s < 0.4:
            q_impr.append("Add more detail; aim for 4–8 concise sentences")
        if clr_s >= 0.8:
            q_strengths.append("Clear writing and sentence structure")
        elif clr_s < 0.4:
            q_impr.append("Simplify sentences and avoid filler words")
        if str_s >= 0.7:
            q_strengths.append("Structured response (STAR-like)")
        else:
            q_impr.append("Add brief structure: context, actions, and result")
        if tech_s >= 0.7:
            q_strengths.append("Solid technical depth/examples")
        else:
            q_impr.append("Include concrete technical details, figures, or examples")

        strengths.extend(q_strengths)
        improvements.extend(q_impr)

        items.append({
            "index": idx,
            "question": q,
            "answer_excerpt": a[:180] + ("…" if len(a) > 180 else ""),
            "answer_word_count": len([t for t in _tokenize(a) if t]),
            "scores": {
                "keyword_coverage": round(kw_cov, 2),
                "length": round(len_s, 2),
                "clarity": round(clr_s, 2),
                "structure": round(str_s, 2),
                "technical_depth": round(tech_s, 2),
                "overall": round(q_score, 2),
            },
            "tips": q_impr[:3],
        })

    overall = sum(total_scores) / max(1, len(total_scores))
    return {
        "items": items,
        "strengths": strengths,
        "improvements": improvements,
        "overall": overall,
    }


def _enhanced_heuristic_feedback(qnas: List[Dict[str, str]]) -> Dict[str, Any]:
    total_questions = len(qnas)
    answered = sum(1 for qa in qnas if (qa.get("answer") or "").strip())
    completeness = answered / max(1, total_questions)

    detail = _build_per_question_feedback(qnas)
    # final score blend: 30% completeness, 70% per-question quality
    blended = 0.30 * completeness + 0.70 * detail["overall"]
    score = int(round(blended * 100))

    strengths = [f"Answered {answered} of {total_questions} questions"] if answered else []
    strengths.extend(detail["strengths"][:5])

    improvements = []
    if answered < total_questions:
        improvements.append("Answer all questions for better completeness")
    improvements.extend(detail["improvements"][:5])

    suggestions = [
        "Use STAR (Situation, Task, Action, Result) to structure behavioral answers",
        "Target 4–8 concise sentences per answer with concrete examples and metrics",
        "Mirror key terms from the question in your answer to ensure coverage",
        "Close with outcomes/impact; quantify where possible",
    ]

    return {
        "score": score,
        "summary": "Heuristic feedback based on coverage, clarity, structure, and depth.",
        "strengths": strengths[:5],
        "improvements": improvements[:5],
        "suggestions": suggestions,
        "metrics": {
            "completeness": round(completeness, 2),
            "quality_overall": round(detail["overall"], 2),
            "total_questions": total_questions,
            "answered": answered,
        },
        "per_question": detail["items"],
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
        enhanced = _enhanced_heuristic_feedback(qnas)
        return {"session_id": session_id, **enhanced}

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
