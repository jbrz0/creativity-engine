from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import os
import re
from src.processing.creativity.preprocess import PreprocessResult
from src.processing.creativity.graph_enrich import GraphEnrichResult

_SERENDIPITY_CACHE: List[str] | None = None

def _load_serendipity_corpus() -> List[str]:
    # Placeholder implementation if file not found
    global _SERENDIPITY_CACHE
    if _SERENDIPITY_CACHE is not None:
        return _SERENDIPITY_CACHE

    # Modified path for v2 structure, or fallback
    # Assuming we might want to drop some .md files in src/resources later
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "resources", "initial-info"))
    
    ideas: List[str] = []
    if os.path.exists(base):
        try:
            for root, _, files in os.walk(base):
                for f in files:
                    if f.lower().endswith(('.md', '.txt')):
                        p = os.path.join(root, f)
                        try:
                            with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                                text = fh.read()
                                for line in text.splitlines():
                                    s = line.strip()
                                    if len(s) > 60 and not s.startswith('#'):
                                        ideas.append(s)
                        except Exception:
                            pass
        except Exception:
            pass
    
    if not ideas:
        # Fallback seeds
        ideas = [
            "Consider the role of entropy in information systems.",
            "Biological mimicry often yields robust engineering solutions.",
            "Fractal patterns appear in both nature and data structures.",
            "The map is not the territory; the model is not the reality.",
            "Feedback loops can stabilize or destabilize depending on delay.",
            "Constraint breeds creativity.",
            "Navigate the space between order and chaos.",
        ]

    _SERENDIPITY_CACHE = ideas[:2000]
    return _SERENDIPITY_CACHE

def _top_k_serendipity(prompt: str, k: int) -> List[str]:
    corpus = _load_serendipity_corpus()
    if not corpus or k <= 0:
        return []
    
    # Simple word overlap heuristic (since we likely don't have embeddings set up yet)
    toks = set(w for w in re.findall(r"[a-zA-Z0-9-]+", prompt.lower()) if len(w) > 2)
    scored: List[Tuple[float, str]] = []
    for line in corpus:
        words = set(w for w in re.findall(r"[a-zA-Z0-9-]+", line.lower()) if len(w) > 2)
        if not words:
            continue
        # Jaccard-ish
        overlap = len(toks & words)
        # Penalize length slightly to avoid just returning long paragraphs?
        score = overlap - 0.0 * len(words) 
        scored.append((score, line))
    
    # Shuffle top scores slightly for randomness if scores are tied
    # But for now just sort
    scored.sort(key=lambda x: x[0], reverse=True)
    # If scores are all 0 (no overlap), return random sample?
    if scored and scored[0][0] <= 0:
        import random
        return random.sample(corpus, min(k, len(corpus)))
        
    return [s for _, s in scored[:k]]


@dataclass(frozen=True)
class AugmentConfig:
    what_if_branches: int
    future_layers: int
    idea_count: int
    converge_bias: float
    serendipity_cross_domain_seeds: int
    graph_hop_distance: int


@dataclass(frozen=True)
class AugmentResult:
    system_prompt: str
    assistant_prelude: str
    user_prompt: str
    controls_applied: Dict[str, int | float]


def _fmt_insights(ge: GraphEnrichResult, max_seeds: int) -> str:
    parts: List[str] = []
    if ge.insights.top_nodes:
        tops = ", ".join(f"{kw} (deg {deg})" for kw, deg in ge.insights.top_nodes[:max_seeds])
        parts.append(f"- Central concepts: {tops}")
    if ge.insights.bridges:
        bridges = ", ".join(f"{a} ↔ {b} (L={L})" for a, b, L in ge.insights.bridges[:max_seeds])
        parts.append(f"- Bridge paths: {bridges}")
    parts.append(f"- Graph size: {ge.insights.node_count} nodes, {ge.insights.edge_count} edges")
    return "\n".join(parts)


def _cross_domain_seeds(pre: PreprocessResult, k: int) -> List[str]:
    if k <= 0:
        return []
    kw = pre.keywords[: max(0, k // 2)]
    pulled = _top_k_serendipity(pre.cleaned_prompt, k - len(kw))
    return [*kw, *pulled]


def build_messages(
    *,
    pre: PreprocessResult,
    ge: GraphEnrichResult,
    cfg: AugmentConfig,
    model_hint: str | None = None,
    slider_dials: Dict[str, int] | None = None,
) -> AugmentResult:
    seeds = _cross_domain_seeds(pre, cfg.serendipity_cross_domain_seeds)
    insights_md = _fmt_insights(ge, max_seeds=max(3, cfg.serendipity_cross_domain_seeds))

    system = (
        "You are **Creativity+**, a rigorous yet playful thinking partner.\n"
        "Your job: transform a prompt into a **structured, shippable exploration**.\n\n"
        "Requirements:\n"
        f"- Produce **Markdown** with crisp headings and skimmable lists.\n"
        f"- Generate **{max(1, cfg.idea_count)}** distinct idea{'s' if cfg.idea_count != 1 else ''} unless the user explicitly asks for one.\n"
        f"- Explore **what-if branches**: {cfg.what_if_branches} branch(es); each up to {cfg.future_layers} future layer(s) deep.\n"
        "- Balance speculation with practicality: for every speculative branch, give 1–2 concrete actions or testable artifacts.\n"
        "- Minimize fluff; prefer specific, verifiable, or falsifiable statements.\n"
        "- Use short paragraphs and bullets. Include call-outs where helpful.\n"
        "- If the user asked for code, include concise examples and assumptions.\n"
    )
    if model_hint:
        system += f"\nModel context hint: {model_hint}\n"

    dial_lines = ""
    if slider_dials:
        spec = slider_dials.get("speculation")
        rand = slider_dials.get("randomness")
        density = slider_dials.get("ideas")
        line_parts = []
        if spec is not None:
            line_parts.append(f"Speculation dial: **{spec}/10**")
        if rand is not None:
            line_parts.append(f"Creative randomness: **{rand}/10**")
        if density is not None:
            line_parts.append(f"Idea density target: **{density}** core nodes")
        if line_parts:
            dial_lines = "### Creative Dials\n" + "\n".join(f"- {part}" for part in line_parts) + "\n\n"

    assistant = (
        "### Controls Snapshot\n"
        f"- What-if branches: **{cfg.what_if_branches}** (depth **{cfg.future_layers}**)\n"
        f"- Idea count target: **{cfg.idea_count}** (converge bias **{cfg.converge_bias}**)\n"
        f"- Serendipity seeds: **{cfg.serendipity_cross_domain_seeds}** (graph hop distance **{cfg.graph_hop_distance}**)\n\n"
        f"{dial_lines}"
        "### Graph Insights\n"
        f"{insights_md}\n\n"
        "### Serendipity Seeds\n"
        + (", ".join(seeds) if seeds else "_(none)_")
        + "\n\n"
        "### Output Format\n"
        "Use this section structure unless the user requested a format:\n"
        "1. **Overview** – the core take, constraints, and key trade-offs.\n"
        "2. **What-ifs** – numbered branches with depth where useful.\n"
        "3. **Cross-domain links** – surprising analogies and transfers.\n"
        "4. **Concrete next steps** – specific actions, prototypes, or tests.\n"
        "5. **Assumptions & risks** – note hidden constraints or fragility.\n"
    )

    user = pre.cleaned_prompt

    return AugmentResult(
        system_prompt=system,
        assistant_prelude=assistant,
        user_prompt=user,
        controls_applied={
            "what_if_branches": cfg.what_if_branches,
            "future_layers": cfg.future_layers,
            "idea_count": cfg.idea_count,
            "converge_bias": cfg.converge_bias,
            "serendipity_cross_domain_seeds": cfg.serendipity_cross_domain_seeds,
            "graph_hop_distance": cfg.graph_hop_distance,
        },
    )
