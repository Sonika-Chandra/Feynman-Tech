"""
Stand-in for the AI module with the SAME function shapes and no API calls.
Turn on with USE_FAKE_AI=1 in .env. Used for building the interface and for tests without using any quota.
"""
MAX_ROUNDS = 5
DIAGRAM = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">'
    '<ellipse cx="200" cy="150" rx="160" ry="110" fill="none" stroke="#1b1214" stroke-width="3"/>'
    '<ellipse cx="200" cy="150" rx="60" ry="40" fill="#e9dcc3" stroke="#1b1214" stroke-width="2"/>'
    '<rect x="270" y="110" width="50" height="30" fill="none" stroke="#1b1214" stroke-width="2"/>'
    '<circle cx="200" cy="150" r="12" fill="#ffffff" stroke="#1b1214"/><text x="196" y="155" font-size="14">1</text>'
    '<circle cx="295" cy="125" r="12" fill="#ffffff" stroke="#1b1214"/><text x="291" y="130" font-size="14">2</text>'
    '<circle cx="90" cy="150" r="12" fill="#ffffff" stroke="#1b1214"/><text x="86" y="155" font-size="14">3</text>'
    '</svg>'
)
QUESTIONS = [
    ("In your own words, what is the main idea of this topic?", False),
    ("Look at the diagram. Can you name the parts marked 1, 2 and 3?", True),
    ("What are the main steps, in order?", False),
    ("What does each step produce?", False),
    ("Why is the last step important?", False),
]


def opening_question(source_text):
    q, wb = QUESTIONS[0]
    return {"next_question": q, "should_stop": False, "round": 1, "needs_whiteboard": wb, "diagram_svg": DIAGRAM if wb else ""}


def next_question(source_text, conversation_history, new_user_reply):
    asked = sum(1 for m in conversation_history if m["role"] == "ai")
    if asked >= MAX_ROUNDS:
        return {"next_question": "", "should_stop": True, "round": asked, "needs_whiteboard": False, "diagram_svg": ""}
    q, wb = QUESTIONS[asked]
    return {"next_question": q, "should_stop": False, "round": asked + 1, "needs_whiteboard": wb, "diagram_svg": DIAGRAM if wb else ""}


def describe_drawing(question, image_bytes, mime_type="image/png"):
    return "A labelled box diagram with two arrows (fake description for testing)."


def final_score(source_text, transcript):
    def c(score, text):
        return {"score": score, "justification": text}
    return {
        "scores": {
            "accuracy": c(7, "Most statements match the notes."),
            "completeness": c(6, "Two key ideas were missing."),
            "consistency": c(9, "No contradictions found."),
            "clarity": c(8, "Clear and well ordered."),
        },
        "overall": 75,
        "mistakes": ["Confused the order of the two stages."],
        "summary": "You explained the main idea well. Review the order of the steps.",
    }


def full_package(source_text, transcript, language="English", include_fact_check=True, include_notes=True, score=None):
    score = score or final_score(source_text, transcript)
    report = (
        "# Mistake Report\n\n## Score Summary\n- Overall: 75/100\n\n## Mistakes\n\n"
        "### Concept Misunderstood\nThe order of the two stages.\n\n"
        "### Correct Explanation\nThe first stage happens before the second.\n\n"
        "### Recommended Review\nRedraw the diagram of the stages.\n"
    )
    return {
        "score": score,
        "fact_check": {"findings": "No suspected errors found.", "sources": []} if include_fact_check else None,
        "report_markdown": report,
        "gaps": [{"concept_misunderstood": "The order of the two stages.",
                  "correct_explanation": "The first stage happens before the second, because the second uses what the first produces.",
                  "recommended_review": "Redraw the diagram of the stages.",
                  "what_student_said": "You described both stages but swapped their order.",
                  "why_it_matters": "The order explains why each stage needs the other.",
                  "practice_question": "Which stage comes first, and what does it hand to the next one?"}],
        "strengths": ["You explained the main idea clearly.", "Your examples matched the notes."],
        "study_plan": ["Redraw the stages diagram from memory.", "Compare it with your notes.", "Explain the order out loud again."],
        "question_feedback": [{"question": "In your own words, what is the main idea of this topic?",
                               "answer_summary": "You gave a clear overview of the topic.",
                               "feedback": "Good overview. Add the order of the steps to make it complete."}],
        "notes": {"language": language, "notes": "## Notes\n- Review the stage order.",
                  "notes_translated": "(fake translated notes)"} if include_notes else None,
    }


def status():
    return {"model": "fake", "models": ["fake"], "key_ending": None}


def speak_wav(text, voice="Aoede"):
    raise RuntimeError("The AI voice is not available in demo mode. The browser voice is used instead.")


def better_titles(sections):
    raise RuntimeError("demo mode")
