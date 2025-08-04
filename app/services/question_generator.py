import google.generativeai as genai
import os

# need debugging, hardcoded for testing
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

genai.configure(api_key="AIzaSyAhiDuf5yk4_5WQ2Hg9c84e7A_voWADvO0")


def generate_questions(role: str, skills: list, experience: int) -> list:
    prompt = f"""
    You are an AI interview assistant. Generate 10 technical interview questions for a candidate applying for the role of {role}.
    The candidate has {experience} years of experience and the following skills: {', '.join(skills)}.
    The questions should be a mix of theoretical and practical ones, but not MCQs.

    Return ONLY a valid Python list of strings, where each string is a question. Do NOT include explanations, numbering, or any other text.
    """

    model = genai.GenerativeModel("gemini-1.5-flash")
    #.generate_content(promopt) is gemini provided method
    response = model.generate_content(prompt)

    # Clean and split response
    if hasattr(response, "text"):
        return response.text.strip().split("\n")
    return ["Error generating questions"]

