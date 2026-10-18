"""
Stand-in for the AI module with the SAME function shapes and no API calls.
Turn on with USE_FAKE_AI=1 in .env. Used for building the interface and for tests without using any quota.
"""
MAX_ROUNDS = 5
DIAGRAM = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480" font-family="Arial" font-size="16" font-weight="bold" text-anchor="middle"><rect x="30" y="30" width="580" height="420" rx="46" fill="#e8f1d8" stroke="#1b1214" stroke-width="6"/><rect x="46" y="46" width="548" height="388" rx="36" fill="#f6fbe9" stroke="#1b1214" stroke-width="2.5"/><path d="M330 95 C420 70 540 100 545 190 C550 280 520 395 410 400 C330 404 300 330 305 250 C308 180 280 110 330 95 Z" fill="#cfe8f5" stroke="#1b1214" stroke-width="3"/><ellipse cx="155" cy="190" rx="68" ry="58" fill="#e7c9d6" stroke="#1b1214" stroke-width="3"/><circle cx="150" cy="188" r="20" fill="#b97a96" stroke="#1b1214" stroke-width="2"/><ellipse cx="130" cy="340" rx="44" ry="24" fill="#7fc47a" stroke="#1b1214" stroke-width="2.5" transform="rotate(-18 130 340)"/><path d="M95 345 L162 330 M100 336 L158 322" stroke="#3d7a3a" stroke-width="2" fill="none"/><ellipse cx="255" cy="385" rx="38" ry="20" fill="#7fc47a" stroke="#1b1214" stroke-width="2.5" transform="rotate(12 255 385)"/><path d="M225 388 L283 380" stroke="#3d7a3a" stroke-width="2" fill="none"/><ellipse cx="270" cy="95" rx="40" ry="20" fill="#7fc47a" stroke="#1b1214" stroke-width="2.5" transform="rotate(-8 270 95)"/><path d="M240 98 L298 90" stroke="#3d7a3a" stroke-width="2" fill="none"/><ellipse cx="240" cy="270" rx="40" ry="19" fill="#f2b28c" stroke="#1b1214" stroke-width="2.5" transform="rotate(35 240 270)"/><path d="M214 258 C226 272 218 262 232 276 C242 286 236 274 252 286" stroke="#b5532a" stroke-width="2" fill="none"/><path d="M92 90 C120 70 150 110 180 92 C210 74 220 118 240 108" fill="none" stroke="#1b1214" stroke-width="3"/><path d="M92 112 C120 92 150 132 180 114 C210 96 220 140 240 130" fill="none" stroke="#1b1214" stroke-width="3"/><path d="M400 410 C440 405 470 425 500 415" fill="none" stroke="#1b1214" stroke-width="3"/><circle cx="100" cy="270" r="4" fill="#1b1214"/><circle cx="112" cy="262" r="4" fill="#1b1214"/><circle cx="90" cy="282" r="4" fill="#1b1214"/><circle cx="118" cy="280" r="4" fill="#1b1214"/><circle cx="40" cy="240" r="15" fill="#ffffff" stroke="#1b1214" stroke-width="2"/><text x="40" y="246">1</text><circle cx="56" cy="150" r="15" fill="#ffffff" stroke="#1b1214" stroke-width="2"/><text x="56" y="156">2</text><circle cx="155" cy="190" r="15" fill="#ffffff" stroke="#1b1214" stroke-width="2"/><text x="155" y="196">3</text><circle cx="430" cy="240" r="15" fill="#ffffff" stroke="#1b1214" stroke-width="2"/><text x="430" y="246">4</text><circle cx="130" cy="340" r="15" fill="#ffffff" stroke="#1b1214" stroke-width="2"/><text x="130" y="346">5</text><circle cx="240" cy="270" r="15" fill="#ffffff" stroke="#1b1214" stroke-width="2"/><text x="240" y="276">6</text><circle cx="165" cy="102" r="15" fill="#ffffff" stroke="#1b1214" stroke-width="2"/><text x="165" y="108">7</text></svg>'
)
QUESTIONS = [
    ("In your own words, what is the main idea of this topic?", False),
    ("Look at the diagram. Can you name the parts marked 1 to 7?", True),
    ("What are the main steps, in order?", False),
    ("What does each step produce?", False),
    ("Why is the last step important?", False),
]


def opening_question(source_text, time_limit=0):
    q, wb = QUESTIONS[0]
    return {"next_question": q, "should_stop": False, "round": 1, "needs_whiteboard": wb, "diagram_svg": DIAGRAM if wb else ""}


def next_question(source_text, conversation_history, new_user_reply, time_limit=0):
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


def full_package(source_text, transcript, language="English", include_notes=True, score=None):
    score = score or final_score(source_text, transcript)
    report = (
        "# Mistake Report\n\n## Score Summary\n- Overall: 75/100\n\n## Mistakes\n\n"
        "### Concept Misunderstood\nThe order of the two stages.\n\n"
        "### Correct Explanation\nThe first stage happens before the second.\n\n"
        "### Recommended Review\nRedraw the diagram of the stages.\n"
    )
    return {
        "score": score,
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
    return {"model": "fake", "models": ["fake"], "key_ending": None, "requests": 0}


def speak_wav(text, voice="Aoede"):
    raise RuntimeError("The AI voice is not available in demo mode. The browser voice is used instead.")


def better_titles(sections):
    raise RuntimeError("demo mode")


def use_key(key):
    pass


def usage(key):
    return 0


def check_key():
    return {"ok": True, "model": "fake", "reply": "OK"}


def server_key():
    return "fake"


def friendly_error(e):
    from ai import ai_module
    return ai_module.friendly_error(e)
