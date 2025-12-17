from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

from src.processing.creativity.graph_stub import GraphClient, GraphInsight
from src.processing.creativity.preprocess import PreprocessResult


@dataclass(frozen=True)
class GraphEnrichResult:
    created_nodes: int
    created_edges: int
    created_typed_edges: int
    insights: GraphInsight
    fallback: Dict[str, int | str] | None = None


logger = logging.getLogger(__name__)


def _fallback_result(pre: PreprocessResult, *, reason: str | None = None) -> GraphEnrichResult:
    # Lightweight, non-graph fallback insight so metadata isn't all zeros
    top: List[Tuple[str, int]] = [(k, 1) for k in pre.keywords[:5]]
    bridges: List[Tuple[str, str, int]] = []
    n = len(set(pre.keywords))
    m = len(pre.pairs)
    approx = GraphInsight(top_nodes=top, bridges=bridges, node_count=n, edge_count=m)
    fallback_meta: Dict[str, int | str] = {"estimated_nodes": n, "estimated_edges": m}
    if reason:
        fallback_meta["reason"] = reason
    return GraphEnrichResult(
        created_nodes=0,
        created_edges=0,
        created_typed_edges=0,
        insights=approx,
        fallback=fallback_meta,
    )


async def graph_enrich(gc: GraphClient, pre: PreprocessResult) -> GraphEnrichResult:
    if not gc.available:
        return _fallback_result(pre, reason="graph_unavailable")

    unique_nodes: List[str] = []
    seen = set()
    for name in [*pre.keywords, *pre.graph_nodes]:
        key = name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique_nodes.append(name)

    try:
        n = await gc.upsert_concepts(unique_nodes)

        typed_task = asyncio.create_task(gc.upsert_typed_relationships(pre.graph_relationships))
        related_task = asyncio.create_task(gc.upsert_related(pre.pairs))
        typed, m = await asyncio.gather(typed_task, related_task)
        ins = await gc.insights()
        return GraphEnrichResult(created_nodes=n, created_edges=m, created_typed_edges=typed, insights=ins)
    except Exception as exc:  # pragma: no cover - requires live graph connection issues
        logger.warning("Graph enrichment failed; falling back to approximate metadata: %s", exc)
        try:
            gc.mark_defunct()
        except Exception:
            pass
        return _fallback_result(pre, reason="graph_error")
