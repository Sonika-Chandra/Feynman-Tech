"""
Honesty checks that run on the server with no AI request:
  - copy overlap: how much of an answer is lifted word-for-word from the study notes,
  - paste attempts and tab switches reported by the page,
and the badge a finished session earns. A flagged session earns no badge.
"""
import json
import re

PASTE_LIMIT = 1          # one blocked paste attempt is enough to flag
TAB_LIMIT = 3            # leaving the page this many times flags the session
OVERLAP_LIMIT = 0.5      # half of an answer's 6-word runs found in the notes
NGRAM = 6
MIN_WORDS = 12           # shorter answers are not checked (a short answer can match by chance)

TIERS = [(90, "Platinum", "\U0001F48E"), (80, "Gold", "\U0001F947"), (60, "Silver", "\U0001F948"), (40, "Bronze", "\U0001F949")]


def _words(text):
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def copy_overlap(answer, material):
    """Fraction (0 to 1) of the answer's 6-word runs that appear in the material in the same order."""
    a = _words(answer)
    if len(a) < MIN_WORDS:
        return 0.0
    m = _words(material)
    notes = {tuple(m[i:i + NGRAM]) for i in range(len(m) - NGRAM + 1)}
    runs = [tuple(a[i:i + NGRAM]) for i in range(len(a) - NGRAM + 1)]
    return round(sum(r in notes for r in runs) / len(runs), 2) if runs else 0.0


def empty():
    return {"paste_attempts": 0, "tab_switches": 0, "copied_answers": 0, "max_overlap": 0.0}


def load(raw):
    base = empty()
    try:
        base.update(json.loads(raw) if raw else {})
    except (TypeError, ValueError):
        pass
    return base


def add_answer(state, answer, material, paste_attempts=0, tab_switches=0):
    state = dict(state)
    state["paste_attempts"] += max(0, int(paste_attempts or 0))
    state["tab_switches"] += max(0, int(tab_switches or 0))
    overlap = copy_overlap(answer, material)
    state["max_overlap"] = max(state["max_overlap"], overlap)
    if overlap >= OVERLAP_LIMIT:
        state["copied_answers"] += 1
    return state


def verdict(state):
    reasons = []
    if state["paste_attempts"] >= PASTE_LIMIT:
        reasons.append(f"Tried to paste text {state['paste_attempts']} time(s)")
    if state["tab_switches"] >= TAB_LIMIT:
        reasons.append(f"Left the page {state['tab_switches']} times")
    if state["copied_answers"]:
        reasons.append(f"{state['copied_answers']} answer(s) copied from the notes")
    return {"flagged": bool(reasons), "reasons": reasons, "paste_attempts": state["paste_attempts"],
            "tab_switches": state["tab_switches"], "max_overlap": state["max_overlap"]}


def badge(overall, flagged):
    if flagged:
        return {"name": "Flagged", "icon": "\u26A0", "tier": "flagged"}
    if overall is None:
        return None
    for floor, name, icon in TIERS:
        if overall >= floor:
            return {"name": name, "icon": icon, "tier": name.lower()}
    return {"name": "Keep going", "icon": "\U0001F331", "tier": "start"}


def profile(rows):
    """rows: finished sessions oldest first, each {overall, flagged, filename, topic}. Returns the collection shown on the profile."""
    clean = [r for r in rows if r["overall"] is not None and not r["flagged"]]
    tiers = {name.lower(): sum(1 for r in clean if badge(r["overall"], False)["tier"] == name.lower())
             for _, name, _ in TIERS}
    improved = False
    groups = {}
    for r in clean:
        groups.setdefault((r["filename"], r["topic"]), []).append(r["overall"])
    for scores in groups.values():
        if len(scores) >= 2 and max(scores[1:]) - scores[0] >= 10:
            improved = True
    specials = [
        {"name": "First steps", "icon": "\U0001F463", "desc": "Finish your first honest session", "earned": len(clean) >= 1},
        {"name": "Improver", "icon": "\U0001F4C8", "desc": "Raise a topic score by 10 points on a retry", "earned": improved},
        {"name": "Honest scholar", "icon": "\U0001F6E1", "desc": "Finish 5 sessions with no integrity flags", "earned": len(clean) >= 5},
        {"name": "Near perfect", "icon": "\U0001F31F", "desc": "Score 95 or more", "earned": any(r["overall"] >= 95 for r in clean)},
    ]
    scored = [r["overall"] for r in clean]
    return {"sessions": len(rows), "clean": len(clean), "flagged": sum(1 for r in rows if r["flagged"]),
            "average": round(sum(scored) / len(scored)) if scored else None, "best": max(scored) if scored else None,
            "tiers": tiers, "specials": specials}
