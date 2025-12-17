from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

_MD_H2 = re.compile(r"^\s*#{2,}\s+", flags=re.MULTILINE)
_WS_MULTI = re.compile(r"[ \t]+")
_NL_MULTI = re.compile(r"\n{3,}")

_PLACEHOLDER_PATTERNS = [
    "*(summary)*",
    "*(branch)*",
    "*(analogy)*",
    "[ ] *(action)*",
    "*(assumption/risk)*",
]


@dataclass(frozen=True)
class PostprocessResult:
    text: str
    metadata: Dict[str, Any]


def cleanup_output(md: str) -> str:
    """Post-fix formatting issues that can make the response look cut off.
    - Dedupe consecutive identical lines in the tail
    - If the text ends with an unfinished heading, drop that dangling heading
    - Ensure final line ends with sentence punctuation
    """
    if not md:
        return ""
        
    tail = md[-1600:]
    lines = tail.splitlines()
    cleaned: list[str] = []
    prev_norm = None
    for ln in lines:
        n = ln.strip().lower()
        if prev_norm is not None and n and n == prev_norm:
            # drop duplicate consecutive line
            continue
        cleaned.append(ln)
        if n:
            prev_norm = n
    new_tail = "\n".join(cleaned)
    new_md = md[:-len(tail)] + new_tail if len(md) > len(tail) else new_tail

    # Remove dangling final heading
    m = re.search(r"(^##[^\n]+)$\s*$", new_md, flags=re.MULTILINE)
    if m and m.end() > len(new_md) - 2:
        new_md = new_md[: m.start()].rstrip()

    # Ensure terminal punctuation
    end = new_md.rstrip()
    if end and not end.endswith((".", "!", "?", "`", "]", "}") ):
        new_md = end + "."
    return new_md


def _normalize_whitespace(md: str) -> str:
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    md = _WS_MULTI.sub(" ", md)
    md = _NL_MULTI.sub("\n\n", md)
    return md.strip() + "\n"


def postprocess_markdown(*, draft_text: str, model_used: str, usage: Dict[str, Any], graph_meta: Dict[str, Any], controls_resolved: Dict[str, Any], max_chars: int = 12000) -> PostprocessResult:
    md = draft_text
    
    # Run cleanup first
    md = cleanup_output(md)
    
    md = _normalize_whitespace(md)
    # Find all h2/h3 headings
    headings = re.findall(r"^\s*#{2,3}\s+(.+)", md, flags=re.MULTILINE)
    # Basic cleanup
    md = md.strip()
    # Truncate to max_chars if provided, trying to preserve whole sentences
    truncated = False
    if max_chars is not None and len(md) > max_chars:
        end = md.rfind(".", 0, max_chars)
        if end != -1:
            md = md[: end + 1]
            truncated = True
        else:
            md = md[:max_chars]
            truncated = True

    metadata: Dict[str, Any] = {
        "model": model_used,
        "usage": {
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        },
        "controls": controls_resolved,
        "graph": graph_meta,
        "structure": {"headings": [h.strip() for h in headings], "was_truncated": truncated},
    }

    return PostprocessResult(text=md, metadata=metadata)
