"""
Backend glue for reading uploads. The real work is done by Role 4's ingestion package:
    ingestion.extract.extract(path) -> [{"title": str, "text": str}, ...]
"""
from ingestion.errors import ExtractionError  # noqa: F401  (re-exported for app.py)
from ingestion.extract import extract


def load_sections(path):
    return extract(path)
