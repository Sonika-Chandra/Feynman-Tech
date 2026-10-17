"""
Stand-in for the AI module with the SAME function shapes and no API calls.
Turn on with USE_FAKE_AI=1 in .env. P2 can build the whole UI against this without using any quota.
"""
MAX_ROUNDS = 5
QUESTIONS = [
    "Where does this process happen, and what is needed for it?",
    "What are the main steps, in order?",
    "What does each step produce?",
    "Why is that step important?",
    "Can you give a simple example?",
]


def next_question(source_text, conversation_history, new_user_reply):
    asked = sum(1 for m in conversation_history if m["role"] == "ai")
    if asked >= MAX_ROUNDS:
        return {"next_question": "", "should_stop": True, "round": asked}
    return {"next_question": QUESTIONS[asked], "should_stop": False, "round": asked + 1}


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


def full_package(source_text, transcript, language="Kannada"):
    score = final_score(source_text, transcript)
    report = (
        "# Mistake Report\n\n## Score Summary\n- Overall: 75/100\n\n## Mistakes\n\n"
        "### Concept Misunderstood\nThe order of the two stages.\n\n"
        "### Correct Explanation\nThe first stage happens before the second.\n\n"
        "### Recommended Review\nRedraw the diagram of the stages.\n"
    )
    return {
        "score": score,
        "fact_check": {"findings": "No suspected errors found.", "sources": []},
        "report_markdown": report,
        "notes": {"language": language, "notes": "## Notes\n- Review the stage order.",
                  "notes_translated": "(fake translated notes)"},
    }


def transcribe(data, mime_type):
    return "(fake transcript of the audio answer)"
