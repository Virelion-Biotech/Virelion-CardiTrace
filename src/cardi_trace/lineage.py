"""Artifact lineage graph and graph queries."""
from __future__ import annotations

from collections import defaultdict, deque
from .models import LineageEdge


class LineageGraph:
    def __init__(self) -> None:
        self.nodes: set[str] = set()
        self.edges: list[LineageEdge] = []
        self._out: dict[str, set[str]] = defaultdict(set)
        self._in: dict[str, set[str]] = defaultdict(set)

    def add_node(self, node_id: str) -> None:
        self.nodes.add(node_id)

    def add_edge(self, source_id: str, target_id: str, relation: str = "derived_from", run_id: str | None = None, metadata: dict | None = None) -> LineageEdge:
        self.add_node(source_id); self.add_node(target_id)
        if source_id == target_id or self._reachable(target_id, source_id):
            raise ValueError("Lineage edge would introduce a cycle")
        edge = LineageEdge(source_id, target_id, relation, run_id, metadata or {})
        if not any(e.source_id == source_id and e.target_id == target_id and e.relation == relation for e in self.edges):
            self.edges.append(edge); self._out[source_id].add(target_id); self._in[target_id].add(source_id)
        return edge

    def _reachable(self, start: str, target: str) -> bool:
        seen = set(); q = deque([start])
        while q:
            node = q.popleft()
            if node == target: return True
            if node in seen: continue
            seen.add(node); q.extend(self._out[node])
        return False

    def ancestors(self, node_id: str) -> set[str]:
        return self._walk(node_id, self._in)

    def descendants(self, node_id: str) -> set[str]:
        return self._walk(node_id, self._out)

    @staticmethod
    def _walk(node_id: str, graph: dict[str, set[str]]) -> set[str]:
        result, q = set(), deque(graph[node_id])
        while q:
            node = q.popleft()
            if node in result: continue
            result.add(node); q.extend(graph[node])
        return result

    def topological(self) -> list[str]:
        indegree = {n: len(self._in[n]) for n in self.nodes}; q = deque(sorted(n for n, d in indegree.items() if d == 0)); order=[]
        while q:
            n=q.popleft(); order.append(n)
            for child in sorted(self._out[n]):
                indegree[child]-=1
                if indegree[child]==0:q.append(child)
        if len(order)!=len(self.nodes): raise ValueError("Lineage graph contains a cycle")
        return order

    def to_dict(self) -> dict:
        return {"nodes": sorted(self.nodes), "edges": [e.to_dict() for e in self.edges]}

    @classmethod
    def from_dict(cls, data: dict) -> "LineageGraph":
        graph=cls()
        for n in data.get("nodes",[]): graph.add_node(n)
        for raw in data.get("edges",[]): graph.add_edge(**raw)
        return graph
