"""
Makes an SVG drawn by the AI safe to show in the browser: only simple drawing shapes are kept, and anything
that could run code or load something from the internet is removed. Returns "" if the SVG is unusable.
"""
import re
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
TAGS = {"svg", "g", "line", "rect", "circle", "ellipse", "path", "polygon", "polyline", "text", "tspan"}
ATTRS = {
    "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "d", "points",
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "font-size",
    "font-family", "font-weight", "text-anchor", "dominant-baseline", "transform", "opacity", "fill-opacity", "stroke-opacity",
}
MAX_CHARS = 24000
MAX_ELEMENTS = 600
BAD_VALUE = re.compile(r"url\s*\(|javascript|data:|<|>|expression", re.I)


def _local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def _clean(el, count):
    if _local(el.tag) not in TAGS:
        return None
    count[0] += 1
    if count[0] > MAX_ELEMENTS:
        raise ValueError("too many elements")
    new = ET.Element(_local(el.tag))
    for k, v in el.attrib.items():
        k = _local(k)
        if k in ATTRS and not BAD_VALUE.search(v):
            new.set(k, v)
    if el.text and el.text.strip() and _local(el.tag) in ("text", "tspan"):
        new.text = el.text.strip()[:60]
    for child in el:
        c = _clean(child, count)
        if c is not None:
            new.append(c)
            if child.tail and child.tail.strip() and _local(el.tag) in ("text", "tspan"):
                c.tail = child.tail.strip()[:60]
    return new


def safe_svg(svg):
    if not isinstance(svg, str):
        return ""
    svg = svg.strip()
    svg = re.sub(r"^```(?:svg|xml)?\s*|\s*```$", "", svg).strip()
    if not svg.lower().startswith("<svg") or len(svg) > MAX_CHARS or "<!ENTITY" in svg or "<!DOCTYPE" in svg:
        return ""
    try:
        root = ET.fromstring(svg)
        if _local(root.tag) != "svg":
            return ""
        cleaned = _clean(root, [0])
    except (ET.ParseError, ValueError):
        return ""
    if cleaned is None or len(cleaned) == 0:
        return ""
    cleaned.set("xmlns", SVG_NS)
    cleaned.attrib.pop("width", None)
    cleaned.attrib.pop("height", None)
    if "viewBox" not in cleaned.attrib:
        cleaned.set("viewBox", "0 0 400 300")
    return ET.tostring(cleaned, encoding="unicode")
