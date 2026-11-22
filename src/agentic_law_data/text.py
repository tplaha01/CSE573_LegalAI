"""Conservative judgment PDF extraction with page-level evidence provenance.

This module does not infer gold rhetorical roles or perform OCR. Character offsets
always address the final cleaned, directly-identified-contact-redacted page text.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
from math import ceil
from pathlib import Path
import re
import unicodedata


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(
    r"(?P<label>\b(?:phone|telephone|mobile|tel|contact\s+(?:no\.?|number))"
    r"\s*(?:no\.?|number)?\s*[:=\-]?\s*)"
    r"(?P<number>\+?\d[\d ()\-]{6,25}\d)", re.I
)
_PAGE_NUMBER = re.compile(r"^(?:page\s+)?(?:\d+|[ivxlcdm]+)(?:\s*(?:of|/)\s*\d+)?$", re.I)
_HEADING = re.compile(
    r"^\s*(?:(?:\d+(?:\.\d+)*|[IVX]+|[A-Z])[.)]\s*)?"
    r"(?P<title>facts(?:\s+of\s+the\s+case)?|brief\s+facts|issues?(?:\s+for\s+determination)?|"
    r"arguments?(?:\s+of\s+(?:the\s+)?(?:parties|appellant|respondent))?|"
    r"submissions?|reasoning(?:\s+and\s+analysis)?|analysis(?:\s+and\s+reasoning)?|"
    r"court'?s\s+reasoning|ratio(?:\s+decidendi)?|decision|conclusion|"
    r"judg(?:e)?ment(?:\s+and\s+order)?)\s*[:.\-]?\s*$", re.I
)
_ABBREVIATIONS = {
    "v", "vs", "mr", "mrs", "ms", "dr", "hon", "no", "nos", "sec", "art", "para",
    "ltd", "pvt", "scc", "s.c.c", "i.e", "e.g", "ors", "anr",
}


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _normalize_lines(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text or "")
    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) != "Cc")
    return [re.sub(r"[\t \u00a0]+", " ", line).strip() for line in text.splitlines()]


def _edge_key(line: str) -> str:
    # Do not merge variable case/citation numbers: only identical boundary text.
    return re.sub(r"\s+", " ", line).strip().casefold()


def redact_contacts(text: str) -> tuple[str, dict[str, int]]:
    """Redact emails and explicitly labelled phone numbers, not names/addresses.

    This is a limited contact-data heuristic, not anonymization or a privacy audit.
    """
    text, emails = _EMAIL.subn("[REDACTED_EMAIL]", text)
    phones = 0

    def replace_phone(match: re.Match) -> str:
        nonlocal phones
        digits = re.sub(r"\D", "", match.group("number"))
        if 8 <= len(digits) <= 15:
            phones += 1
            return match.group("label") + "[REDACTED_PHONE]"
        return match.group(0)

    text = _PHONE.sub(replace_phone, text)
    return text, {"emails": emails, "phones": phones}


def clean_pages(raw_pages: list[str]) -> tuple[list[str], list[dict]]:
    """Clean only repeated boundary lines, boundary page numbers and controls."""
    normalized = [_normalize_lines(text) for text in raw_pages]
    first_counts: Counter = Counter()
    last_counts: Counter = Counter()
    for lines in normalized:
        nonempty = [line for line in lines if line]
        first_counts.update(set(_edge_key(s) for s in nonempty[:2]))
        last_counts.update(set(_edge_key(s) for s in nonempty[-2:]))
    threshold = max(2, ceil(len(raw_pages) * 0.6))
    cleaned, diagnostics = [], []
    for lines in normalized:
        lines = [line for line in lines if line]
        remove = set()
        for index in set(range(min(2, len(lines)))) | set(range(max(0, len(lines) - 2), len(lines))):
            line = lines[index]
            boundary_count = first_counts[_edge_key(line)] if index < 2 else last_counts[_edge_key(line)]
            # Explicit section headings are evidence and must not be stripped.
            repeated = len(line) < 140 and boundary_count >= threshold and not _HEADING.fullmatch(line)
            page_number = bool(_PAGE_NUMBER.fullmatch(line))
            if repeated or page_number:
                remove.add(index)
        text = "\n".join(line for i, line in enumerate(lines) if i not in remove).strip()
        text, redactions = redact_contacts(text)
        cleaned.append(text)
        diagnostics.append({"removed_boundary_lines": len(remove), "redaction_counts": redactions})
    return cleaned, diagnostics


def _role(title: str) -> str:
    value = title.casefold()
    if "fact" in value:
        return "FACTS"
    if value.startswith("issue"):
        return "ISSUE"
    if value.startswith(("argument", "submission")):
        return "ARGUMENTS"
    if "reason" in value or value.startswith(("analysis", "ratio")):
        return "REASONING"
    return "DECISION"


def section_spans(pages: list[str]) -> list[list[dict]]:
    """Return page-local content spans with explicit-heading silver labels.

    The common front-matter JUDGMENT heading cannot label an entire unsectioned
    judgment as a decision. It starts a DECISION span only after another explicit
    rhetorical heading has been seen. Other labels persist onto following pages.
    """
    role, label_source = "UNKNOWN", "unlabeled"
    substantive_heading_seen = False
    all_spans = []
    for text in pages:
        spans = []
        start, cursor = 0, 0
        for line in text.splitlines(keepends=True):
            match = _HEADING.fullmatch(line.strip())
            if match:
                title = match.group("title")
                boilerplate = title.casefold().startswith(("judgment", "judgement")) and not substantive_heading_seen
                if not boilerplate:
                    if text[start:cursor].strip():
                        spans.append({"char_start": start, "char_end": cursor, "section": role, "label_source": label_source})
                    role, label_source = _role(title), "explicit_heading_silver"
                    substantive_heading_seen = True
                    start = cursor + len(line)
            cursor += len(line)
        if text[start:].strip():
            spans.append({"char_start": start, "char_end": len(text), "section": role, "label_source": label_source})
        all_spans.append(spans)
    return all_spans


def _sentence_ranges(text: str, start: int, end: int) -> list[tuple[int, int]]:
    ranges, cursor = [], start
    for match in re.finditer(r"[.!?][\"')\]]*\s+", text[start:end]):
        boundary = start + match.end()
        prefix = text[cursor:start + match.start() + 1]
        token = re.search(r"([A-Za-z.]+)\.$", prefix)
        if token and token.group(1).strip(".").casefold() in _ABBREVIATIONS:
            continue
        a, b = cursor, boundary
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if a < b:
            ranges.append((a, b))
        cursor = boundary
    a, b = cursor, end
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    if a < b:
        ranges.append((a, b))
    return ranges


def build_records(pages: list[str], doc_id: str, source_file: str,
                  chunk_words: int = 350, overlap_words: int = 50) -> tuple[list[dict], list[dict]]:
    """Build model inputs from cleaned pages without crossing page/section spans."""
    if chunk_words < 1 or not 0 <= overlap_words < chunk_words:
        raise ValueError("Require chunk_words >= 1 and 0 <= overlap_words < chunk_words")
    chunks, sentences = [], []
    for page_index, (text, spans) in enumerate(zip(pages, section_spans(pages)), start=1):
        for span in spans:
            shared = {"doc_id": str(doc_id), "section": span["section"],
                      "label_source": span["label_source"], "source_file": source_file}
            words = list(re.finditer(r"\S+", text[span["char_start"]:span["char_end"]]))
            step = chunk_words - overlap_words
            for word_index in range(0, len(words), step):
                selected = words[word_index:word_index + chunk_words]
                a = span["char_start"] + selected[0].start()
                b = span["char_start"] + selected[-1].end()
                content = text[a:b]
                identity = f"{doc_id}:{page_index}:{a}:{b}:{_hash(content)}"
                chunks.append({**shared, "chunk_id": f"{doc_id}_p{page_index}_{_hash(identity)[:16]}",
                               "page_start": page_index, "page_end": page_index,
                               "char_start": a, "char_end": b, "text": content,
                               "text_sha256": _hash(content), "word_count": len(selected)})
                if word_index + chunk_words >= len(words):
                    break
            for a, b in _sentence_ranges(text, span["char_start"], span["char_end"]):
                content = text[a:b]
                identity = f"{doc_id}:{page_index}:{a}:{b}:{_hash(content)}"
                sentences.append({**shared, "sentence_id": f"{doc_id}_s{_hash(identity)[:16]}",
                                  "page": page_index, "char_start": a, "char_end": b,
                                  "text": content, "text_sha256": _hash(content)})
    return chunks, sentences


def _extract_metadata(pages: list[str], doc_id: str, source_file: str) -> dict:
    metadata = {"doc_id": str(doc_id), "source_file": source_file, "page_count": len(pages),
                "extraction_method": "pdfplumber", "cleanup_version": "1.0",
                "court": None, "bench": None, "docket": None, "decision_date": None,
                "metadata_provenance": {}}
    patterns = {
        "court": re.compile(r"(?im)^\s*(SUPREME\s+COURT\s+OF\s+INDIA)\s*$"),
        "bench": re.compile(r"(?im)^\s*(?:BENCH|CORAM|JUDGES?)\s*:\s*(.+)$"),
        "docket": re.compile(r"(?im)^\s*((?:CIVIL|CRIMINAL|WRIT|SPECIAL\s+LEAVE)\s+[^\n]{0,100}"
                             r"(?:APPEAL|PETITION)[^\n]{0,60}\bNOS?\.?\s*[^\n]+)$"),
        "decision_date": re.compile(r"(?im)^\s*(?:DATE\s+OF\s+JUDG(?:E)?MENT|DECIDED\s+ON|DECISION\s+DATE)"
                                    r"\s*[:\-]?\s*(.+)$"),
    }
    for page_number, text in enumerate(pages[:3], start=1):
        for name, pattern in patterns.items():
            if metadata[name] is not None:
                continue
            match = pattern.search(text)
            if not match:
                continue
            value = match.group(1).strip()
            if name == "decision_date":
                parsed = None
                value = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", value, flags=re.I)
                for fmt in ("%d %B %Y", "%d %B, %Y", "%d %b %Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        parsed = datetime.strptime(value.rstrip("."), fmt).date().isoformat()
                        break
                    except ValueError:
                        pass
                if parsed is None:
                    continue
                value = parsed
            metadata[name] = value
            metadata["metadata_provenance"][name] = {"page": page_number,
                                                    "raw": match.group(0).strip(),
                                                    "method": "explicit_header_pattern"}
    return metadata


def extract_pdf(path: Path, doc_id: str, chunk_words: int = 350,
                overlap_words: int = 50) -> dict:
    """Extract a supplied judgment PDF; failures are raised for the caller to log.

    Scanned or image-only pages are reported for OCR; no synthetic text is added.
    For a mapped document, an Indian Kanoon ``doc_id`` is required from the caller.
    """
    if chunk_words < 1 or not 0 <= overlap_words < chunk_words:
        raise ValueError("Require chunk_words >= 1 and 0 <= overlap_words < chunk_words")
    if not str(doc_id).isdigit():
        raise ValueError("doc_id must be the authoritative numeric document identifier")
    import pdfplumber  # Optional until a real judgment PDF is supplied.
    path = Path(path)
    with pdfplumber.open(path) as pdf:
        raw_pages = [page.extract_text() or "" for page in pdf.pages]
    cleaned, diagnostics = clean_pages(raw_pages)
    source_file = path.name
    pages, warnings, ocr_pages = [], [], []
    for page_number, (text, diagnostic) in enumerate(zip(cleaned, diagnostics), start=1):
        if sum(c.isalpha() for c in text) < 20:
            ocr_pages.append(page_number)
            warnings.append(f"page_{page_number}: insufficient extractable text; inspect and OCR if scanned")
        pages.append({"doc_id": str(doc_id), "page": page_number, "text": text,
                      "text_sha256": _hash(text), "redaction_counts": diagnostic["redaction_counts"],
                      "removed_boundary_lines": diagnostic["removed_boundary_lines"], "source_file": source_file})
    chunks, sentences = build_records(cleaned, str(doc_id), source_file, chunk_words, overlap_words)
    metadata = _extract_metadata(cleaned, str(doc_id), source_file)
    metadata["text_pages"] = sum(bool(p.strip()) for p in cleaned)
    metadata["ocr_required_pages"] = ocr_pages
    metadata["privacy_status"] = "limited_email_and_labelled_phone_redaction; manual_review_required"
    if not any(p.strip() for p in cleaned):
        warnings.append("document_has_no_extractable_text")
    if not any(chunk["section"] != "UNKNOWN" for chunk in chunks):
        warnings.append("no_explicit_rhetorical_headings; labels remain UNKNOWN")
    return {"pages": pages, "chunks": chunks, "sentences": sentences,
            "metadata": metadata, "warnings": warnings}
