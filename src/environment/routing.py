"""Shortest-path and feasibility helpers for VNF service chains."""

from __future__ import annotations

from itertools import islice
from typing import Any, Iterable, Sequence

import networkx as nx

try:
    from ..domain.network import Network
    from ..domain.request import Request
    from .constraints import ConstraintChecker, deadline_available, processing_delay, route_is_valid
except ImportError:  # pragma: no cover
    from domain.network import Network
    from domain.request import Request
    from environment.constraints import ConstraintChecker, deadline_available, processing_delay, route_is_valid


def shortest_path(network: Network, source: Any, destination: Any,
                  *, weight: str = "dl") -> list[Any]:
    """Return the shortest graph path between two nodes."""
    return nx.shortest_path(network.G, source, destination, weight=weight)


def shortest_route(network: Network, request: Request, servers: Sequence[Any],
                   *, weight: str = "dl") -> list[Any]:
    """Build a route from source through VNF servers to destination."""
    if len(servers) != len(request.Fr):
        raise ValueError("one placement server is required for every VNF")
    points = [request.st, *servers, request.d]
    route: list[Any] = []
    for source, destination in zip(points[:-1], points[1:]):
        segment = shortest_path(network, source, destination, weight=weight)
        route.extend(segment if not route else segment[1:])
    return route


def route_delay(network: Network, route: Sequence[Any], servers: Sequence[Any],
                vnfs: Sequence[Any], vnf_ids: Sequence[int]) -> float:
    """Return end-to-end delay of a route and VNF placement."""
    return processing_delay(network, route, servers, vnfs, vnf_ids)


def find_feasible_route(
    network: Network,
    request: Request,
    servers: Sequence[Any],
    *,
    bandwidth: float | None = None,
    vnfs: Sequence[Any] | None = None,
    manager: Any | None = None,
    t1: int = 0,
    t2: int = 1,
    current_time: float = 0,
) -> list[Any] | None:
    """Return a shortest feasible route, or ``None`` if no route qualifies."""
    route = shortest_route(network, request, servers)
    if not route_is_valid(network, route, request.st, request.d, servers):
        return None
    if bandwidth is not None:
        if not ConstraintChecker(network, manager).route(route, bandwidth, t1, t2):
            return None
    if vnfs is not None:
        delay = route_delay(network, route, servers, vnfs, request.Fr)
        if not deadline_available(float(request.dr), current_time, delay):
            return None
    return route


def k_shortest_paths(network: Network, source: Any, destination: Any,
                     *, k: int = 5, weight: str = "dl") -> list[list[Any]]:
    """Return up to ``k`` simple paths ordered by the requested edge weight."""
    if k < 1:
        raise ValueError("k must be positive")
    paths = nx.shortest_simple_paths(network.G, source, destination, weight=weight)
    return list(islice(paths, k))


__all__ = [
    "find_feasible_route", "k_shortest_paths", "route_delay",
    "shortest_path", "shortest_route",
]
