"""Cleaning text and splitting it into topics (sections) that the student can pick from."""
import re

WHOLE = "Whole document"
MAX_SECTION_CHARS = 30000
MIN_BODY = 40

_MD = re.compile(r"^#{1,4}\s+(.+?)\s*#*$")
_NUM = re.compile(r"^(?:\d+(?:\.\d+)*[.)]|[IVXLC]+\.)\s+(\S.*)$")


def clean_text(text):
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").replace("\u200b", "")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)          # words split across lines
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _plain_title(s):
    words = s.split()
    return 3 <= len(s) <= 70 and len(words) <= 8 and s[0].isupper() and s[-1] not in ".,;!?"


def heading_title(lines, i):
    """Returns the heading text if lines[i] looks like a heading, otherwise None."""
    s = lines[i].strip()
    if not s or len(s) > 90:
        return None
    m = _MD.match(s)
    if m:
        return m.group(1).strip()
    m = _NUM.match(s)
    if m and len(s) <= 80 and len(s.split()) <= 12 and s[-1] not in ".,;!?":
        return s
    prev_blank = i == 0 or not lines[i - 1].strip()
    nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
    if prev_blank and nxt and len(nxt) > len(s) and _plain_title(s):
        return s.rstrip(":")
    return None


def merge_small(sections):
    """Sections with almost no body are glued onto the previous one instead of becoming a topic."""
    out = []
    for s in sections:
        body = (s.get("text") or "").strip()
        if len(body) < MIN_BODY and out:
            out[-1]["text"] = (out[-1]["text"] + "\n" + s["title"] + "\n" + body).strip()
        elif len(body) < MIN_BODY and not out:
            out.append({"title": s["title"], "text": body})
        else:
            out.append({"title": s["title"], "text": body})
    return [s for s in out if s["text"]]


def finalize(sections):
    """Drops empties, shortens titles, makes titles unique, caps the size of each section."""
    out, seen = [], {}
    for s in sections:
        title = " ".join(str(s.get("title") or "").split())[:90] or "Section"
        body = str(s.get("text") or "").strip()[:MAX_SECTION_CHARS]
        if not body:
            continue
        key = title.lower()
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            title = f"{title} ({seen[key]})"
        out.append({"title": title, "text": body})
    return out


def chunk_by_size(text, limit=6000, target=3500):
    """No headings found: one topic for short text, otherwise 'Part 1', 'Part 2', ..."""
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= limit:
        return [{"title": WHOLE, "text": text}]
    chunks, cur = [], ""
    for p in re.split(r"\n\s*\n", text):
        if cur and len(cur) + len(p) + 2 > target:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    out = []
    for n, c in enumerate(chunks, 1):
        words = " ".join(c.split()[:6])
        out.append({"title": f"Part {n}: {words}", "text": c})
    return finalize(out)


def split_sections(text):
    """Plain or Markdown text -> list of {"title", "text"}."""
    text = clean_text(text)
    if not text:
        return []
    lines = text.split("\n")
    heads = []
    for i in range(len(lines)):
        t = heading_title(lines, i)
        if t:
            heads.append((i, t))
    if len(heads) >= 2:
        secs = []
        intro = "\n".join(lines[: heads[0][0]]).strip()
        if len(intro) >= 80:
            secs.append({"title": "Introduction", "text": intro})
        for k, (i, t) in enumerate(heads):
            end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            secs.append({"title": t, "text": "\n".join(lines[i + 1:end]).strip()})
        merged = finalize(merge_small(secs))
        if len(merged) >= 2:
            return merged
    return chunk_by_size(text)


GENERIC = re.compile(r"^(part\s*\d+|section( \d+)?|whole document|introduction|slide \d+)\b", re.I)
_STOP = set("the a an of and or to in on for with is are was were this that these those it its as by at from be been being which who whom".split())


def is_generic(title):
    return bool(GENERIC.match((title or "").strip()))


def guess_title(text):
    """A readable heading from the first sentence: its first few meaningful words, in Title Case."""
    first = re.split(r"(?<=[.!?])\s|\n", (text or "").strip(), maxsplit=1)[0]
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", first)
    while words and words[0].lower() in _STOP:
        words.pop(0)
    words = words[:6]
    while words and words[-1].lower() in _STOP:
        words.pop()
    if not words:
        return None
    return " ".join(w if w.isupper() and len(w) > 1 else w.capitalize() for w in words)


def retitle_generic(sections):
    """Replaces generic titles ('Part 2: ...') with a heading guessed from the text. Real headings are kept."""
    out = []
    for s in sections:
        t = s["title"]
        if len(sections) > 1 and is_generic(t) and not t.lower().startswith("introduction"):
            t = guess_title(s["text"]) or t
        out.append({"title": t, "text": s["text"]})
    return finalize(out)
