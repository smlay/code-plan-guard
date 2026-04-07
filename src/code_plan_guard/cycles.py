"""v0.3 deterministic rule: cycle detection in import edges."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def find_any_cycle(edges: Iterable[tuple[str, str]]) -> list[str] | None:
    """
    Return one cycle path like [a, b, c, a] if found, else None.
    Uses DFS on directed graph.
    """
    g: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()
    for a, b in edges:
        g[a].append(b)
        nodes.add(a)
        nodes.add(b)

    visiting: set[str] = set()
    visited: set[str] = set()
    parent: dict[str, str | None] = {}

    def _reconstruct(start: str, end: str) -> list[str]:
        # start -> ... -> end and edge end->start exists via back-edge
        path = [end]
        cur = end
        while cur != start and cur in parent and parent[cur] is not None:
            cur = parent[cur]  # type: ignore[assignment]
            path.append(cur)
        path.reverse()
        path.append(start)
        return path

    def dfs(u: str) -> list[str] | None:
        visiting.add(u)
        for v in g.get(u, []):
            if v in visiting:
                return _reconstruct(v, u)
            if v in visited:
                continue
            parent[v] = u
            cyc = dfs(v)
            if cyc:
                return cyc
        visiting.remove(u)
        visited.add(u)
        return None

    for n in sorted(nodes):
        if n in visited:
            continue
        parent[n] = None
        cyc = dfs(n)
        if cyc:
            return cyc
    return None

