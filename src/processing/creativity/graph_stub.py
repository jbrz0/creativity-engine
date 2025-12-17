from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional

@dataclass
class GraphInsight:
    top_nodes: List[Tuple[str, int]]
    bridges: List[Tuple[str, str, int]]
    node_count: int
    edge_count: int

class GraphClient:
    def __init__(self):
        self.available = False

    async def upsert_concepts(self, concepts: List[str]) -> int:
        return 0

    async def upsert_typed_relationships(self, rels: List[Tuple[str, str, str]]) -> Tuple[int, int]:
        return 0, 0

    async def upsert_related(self, pairs: List[Tuple[str, str]]) -> int:
        return 0

    async def insights(self) -> GraphInsight:
        return GraphInsight([], [], 0, 0)

    def mark_defunct(self):
        pass

    async def populate_request_graph(self, run_id: str, nodes: Any, rels: Any) -> Tuple[int, int]:
        return 0, 0
        
    async def analyze_request_graph(self, run_id: str, limit: int) -> List[Tuple[str, int]]:
        return []

    async def clear_request_graph(self, run_id: str):
        pass
