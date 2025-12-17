from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple
import os


_NODE_WS = re.compile(r"\s+")
_NODE_TRIM = re.compile(r"^[`'\"]+|[`'\"]+$")

try:
    from spacy.tokens import Doc  # type: ignore
except Exception:
    Doc = Any  # type: ignore

_SPACY_NLP: Optional[Any] = None


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TOKEN_SPLIT = re.compile(r"[^\w\-']+", flags=re.UNICODE)
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "for", "of", "to", "in",
    "on", "with", "by", "as", "at", "from", "is", "are", "was", "were", "be", "being",
    "been", "it", "this", "that", "these", "those", "i", "you", "we", "they", "he", "she",
    "them", "us", "our", "my", "your", "their", "me", "him", "her", "what", "which",
    "who", "whom", "about", "into", "over", "under", "between", "within", "without",
    "can", "could", "should", "would", "may", "might", "will", "shall", "do", "does",
    "did", "have", "has", "had", "so", "just", "not", "no", "yes",
}


@dataclass(frozen=True)
class PreprocessResult:
    cleaned_prompt: str
    sentences: List[str]
    keywords: List[str]
    pairs: List[Tuple[str, str]]
    graph_nodes: List[str]
    graph_relationships: List[Tuple[str, str, str]]


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_keywords(text: str, max_keywords: int = 50) -> List[str]:
    tokens = _TOKEN_SPLIT.split(text.lower())
    words = [t for t in tokens if t and len(t) > 2 and t not in _STOPWORDS]
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:max_keywords]]


def _cooccurrence_pairs(sentences: List[str], keywords: List[str], max_pairs: int = 200) -> List[Tuple[str, str]]:
    keyset = set(keywords)
    pairs: List[Tuple[str, str]] = []
    for s in sentences:
        toks = [t for t in _TOKEN_SPLIT.split(s.lower()) if t]
        present = [t for t in toks if t in keyset]
        uniq = list(dict.fromkeys(present))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                a, b = uniq[i], uniq[j]
                if a != b:
                    pairs.append((a, b))
                    if len(pairs) >= max_pairs:
                        return pairs
    return pairs


def _get_spacy_nlp() -> Optional[Any]:
    global _SPACY_NLP
    if _SPACY_NLP is not None:
        return _SPACY_NLP
    try:
        import spacy  # type: ignore

        model_name = os.getenv("BG_SPACY_MODEL", "en_core_web_sm")
        _SPACY_NLP = spacy.load(model_name)
    except Exception:
        _SPACY_NLP = None
    return _SPACY_NLP


def _sanitize_phrase(text: str) -> str:
    text = _NODE_TRIM.sub("", text.strip())
    text = _NODE_WS.sub(" ", text)
    if len(text) > 80:
        text = text[:80].rstrip()
    return text


def _span_text(obj: Any) -> str:
    try:
        if hasattr(obj, "text") and hasattr(obj, "subtree"):
            tokens = [t.text for t in obj.subtree if not getattr(t, "is_punct", False)]
        elif hasattr(obj, "text") and hasattr(obj, "__iter__"):
            tokens = [t.text for t in obj if not getattr(t, "is_punct", False)]
        else:
            tokens = [str(obj)]
    except Exception:
        tokens = [str(obj)]
    return _sanitize_phrase(" ".join(tokens))


def _sanitize_rel_type(label: str) -> str:
    label = label.strip().upper()
    label = re.sub(r"[^A-Z0-9]+", "_", label)
    label = label.strip("_")
    if not label:
        return ""
    if label[0].isdigit():
        label = f"A_{label}"
    if len(label) > 40:
        label = label[:40].rstrip("_")
    return label


def _graph_elements_from_doc(
    doc: Doc,
    *,
    limit_nodes: int = 160,
    limit_relationships: int = 240,
) -> Tuple[List[str], List[Tuple[str, str, str]]]:
    nodes: List[str] = []
    rels: List[Tuple[str, str, str]] = []
    seen_nodes: dict[str, str] = {}
    rel_seen: set[Tuple[str, str, str]] = set()

    def _add_node(name: str):
        clean = _sanitize_phrase(name)
        if not clean or len(clean) < 3 or len(clean) > 60:
            return
        key = clean.lower()
        if key not in seen_nodes:
            seen_nodes[key] = clean
            nodes.append(clean)

    for chunk in doc.noun_chunks:
        _add_node(chunk.text)
        if len(nodes) >= limit_nodes:
            break

    for sent in doc.sents:
        for token in sent:
            if token.pos_ not in {"VERB", "AUX"}:
                continue
            lemma = token.lemma_.lower().strip()
            if not lemma:
                continue
            subjects = [c for c in token.children if c.dep_ in {"nsubj", "nsubjpass", "csubj"}]
            if not subjects:
                continue
            targets: List[Any] = []
            for child in token.children:
                if child.dep_ in {"dobj", "obj", "pobj", "attr", "oprd", "dative"}:
                    targets.append(child)
                elif child.dep_ == "prep":
                    pobj = next((gc for gc in child.children if gc.dep_ == "pobj"), None)
                    if pobj is not None:
                        targets.append(pobj)
                elif child.dep_ == "acomp":
                    targets.append(child)
            if not targets:
                continue
            rel_type = ""
            if lemma in {"be"}:
                if any(getattr(t, "pos_", "") == "ADJ" for t in targets):
                    rel_type = "HAS_PROPERTY"
                else:
                    rel_type = "IS_A"
            else:
                rel_type = _sanitize_rel_type(lemma)
            if not rel_type:
                continue
            for subj_tok in subjects:
                subj_text = _span_text(subj_tok)
                _add_node(subj_text)
                for obj_tok in targets:
                    obj_text = _span_text(obj_tok)
                    _add_node(obj_text)
                    src = _sanitize_phrase(subj_text)
                    dst = _sanitize_phrase(obj_text)
                    if not src or not dst or src == dst:
                        continue
                    trip = (src, rel_type, dst)
                    if trip in rel_seen:
                        continue
                    rel_seen.add(trip)
                    rels.append(trip)
                    if len(rels) >= limit_relationships:
                        return nodes[:limit_nodes], rels[:limit_relationships]
    return nodes[:limit_nodes], rels[:limit_relationships]


def extract_graph_elements(
    text: str,
    *,
    sentences: Optional[Sequence[str]] = None,
    keywords: Optional[Sequence[str]] = None,
    doc: Optional[Doc] = None,
    limit_nodes: int = 160,
    limit_relationships: int = 240,
) -> Tuple[List[str], List[Tuple[str, str, str]]]:
    nodes: List[str] = []
    rels: List[Tuple[str, str, str]] = []
    doc_local: Optional[Doc] = doc
    if doc_local is None:
        nlp = _get_spacy_nlp()
        if nlp is not None:
            try:
                doc_local = nlp(text[:8000])  # pragma: no cover
            except Exception:
                doc_local = None
    if doc_local is not None:
        nodes, rels = _graph_elements_from_doc(doc_local, limit_nodes=limit_nodes, limit_relationships=limit_relationships)

    if sentences is None:
        sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    if keywords is None:
        keywords = _extract_keywords(text)[:40]

    if not nodes:
        uniq_keywords: List[str] = []
        seen_kw = set()
        for kw in keywords:
            clean_kw = _sanitize_phrase(kw)
            if clean_kw and clean_kw not in seen_kw:
                seen_kw.add(clean_kw)
                uniq_keywords.append(clean_kw)
        nodes = uniq_keywords[:limit_nodes]

    if not rels:
        pairs = _cooccurrence_pairs(list(sentences), list(keywords), max_pairs=limit_relationships)
        cleaned: List[Tuple[str, str, str]] = []
        for a, b in pairs:
            src = _sanitize_phrase(a)
            dst = _sanitize_phrase(b)
            if not src or not dst or src == dst:
                continue
            cleaned.append((src, "RELATED", dst))
            if len(cleaned) >= limit_relationships:
                break
        rels = cleaned
        # Ensure nodes include endpoints from fallback relations
        node_set = {n.lower(): n for n in nodes}
        for a, _, b in rels:
            if a.lower() not in node_set:
                node_set[a.lower()] = a
                nodes.append(a)
            if b.lower() not in node_set:
                node_set[b.lower()] = b
                nodes.append(b)

    return nodes[:limit_nodes], rels[:limit_relationships]


def preprocess(prompt: str) -> PreprocessResult:
    cleaned = normalize_whitespace(prompt)
    sentences = [s.strip() for s in _SENT_SPLIT.split(cleaned) if s.strip()]
    if not sentences:
        sentences = [cleaned]
    keywords = _extract_keywords(cleaned)[:25]

    nlp_model = _get_spacy_nlp()
    doc_inst: Optional[Doc] = None
    if nlp_model is not None:
        try:
            doc_inst = nlp_model(cleaned[:8000])  # pragma: no cover
        except Exception:
            doc_inst = None
    if doc_inst is not None:
        try:
            chunks = [
                " ".join(tok.lemma_.lower() for tok in chunk if tok.pos_ in {"NOUN", "PROPN", "ADJ"}).strip()
                for chunk in doc_inst.noun_chunks
            ]
            chunks = [c for c in chunks if len(c) > 2]
            for c in chunks:
                if c not in keywords:
                    keywords.append(c)
            keywords = keywords[:40]
        except Exception:
            pass

    pairs = _cooccurrence_pairs(sentences, keywords)
    graph_nodes, graph_relationships = extract_graph_elements(
        cleaned,
        sentences=sentences,
        keywords=keywords,
        doc=doc_inst,
    )
    return PreprocessResult(
        cleaned_prompt=cleaned,
        sentences=sentences,
        keywords=keywords,
        pairs=pairs,
        graph_nodes=graph_nodes,
        graph_relationships=graph_relationships,
    )
