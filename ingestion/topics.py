import re

TOPIC_KEYWORDS = [
    ("introduction", ["introduction", "what is", "overview", "about"]),
    ("history", ["history", "origin", "background"]),
    ("features", ["feature", "characteristic", "advantage"]),
    ("usage", ["use", "application"]),
    ("example", ["example", "demo", "sample"]),
    ("motivation", ["why", "learn", "benefit"]),
    ("conclusion", ["conclusion", "summary"]),
]


def detect_topic(title):
    clean = re.sub(r"[^a-z ]", "", title.lower()).strip()
    for topic, words in TOPIC_KEYWORDS:
        if any(word in clean for word in words):
            return topic
    return clean or "untitled"


def tag_topics(sections):
    for item in sections:
        item["topic"] = detect_topic(item["title"])
    return sections