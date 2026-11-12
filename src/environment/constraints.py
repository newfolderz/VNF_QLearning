"""Feasibility checks for placement and routing decisions.

The functions in this module are pure checks: they never reserve resources.
Reservations are still applied by :class:`domain.allocation.AllocationManager`
after all checks have passed.
"""

from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence

try:
    from ..domain.network import Network
except ImportError:  # pragma: no cover
    from domain.network import Network


def validate_interval(network: Network, t1: int, t2: int) -> None:
    """Validate a half-open reservation interval ``[t1, t2)``."""
    if not isinstance(t1, int) or not isinstance(t2, int):
        raise TypeError("t1 and t2 must be integers")
    if t1 < 0 or t2 <= t1 or t2 > network.max_horizon:
        raise ValueError(
            f"invalid interval [{t1}, {t2}); expected 0 <= t1 < t2 <= "
            f"{network.max_horizon}"
        )


def node_capacity_available(network: Network, node: Any, vnf: Any, t1: int, t2: int) -> bool:
    """Return whether a VNF fits on ``node`` throughout ``[t1, t2)``."""
    validate_interval(network, t1, t2)
    if node not in network.server_nodes:
        return False
    server = network.G.nodes[node]
    return all(
        server["c_use"][t] + vnf.cf <= server["c_cap"] + 1e-9
        and server["r_use"][t] + vnf.rf <= server["r_cap"] + 1e-9
        and server["h_use"][t] + vnf.hf <= server["h_cap"] + 1e-9
        for t in range(t1, t2)
    )


def link_capacity_available(network: Network, u: Any, v: Any, bandwidth: float,
                            t1: int, t2: int) -> bool:
    """Return whether one link can carry ``bandwidth`` in the interval."""
    validate_interval(network, t1, t2)
    if bandwidth < 0 or not network.G.has_edge(u, v):
        return False
    edge = network.G[u][v]
    return all(edge["b_use"][t] + bandwidth <= edge["b_cap"] + 1e-9 for t in range(t1, t2))


def route_edges(route: Sequence[Any]) -> Counter[tuple[Any, Any]]:
    """Count traversals of undirected edges in a route."""
    def edge_key(u: Any, v: Any) -> tuple[Any, Any]:
        try:
            return (u, v) if u <= v else (v, u)
        except TypeError:
            return (u, v) if repr(u) <= repr(v) else (v, u)

    return Counter(
        edge_key(u, v)
        for u, v in zip(route[:-1], route[1:])
    )


def route_capacity_available(network: Network, route: Sequence[Any], bandwidth: float,
                             t1: int, t2: int) -> bool:
    """Check bandwidth, accounting for repeated traversals of an edge."""
    if not route or bandwidth < 0:
        return False
    validate_interval(network, t1, t2)
    for (u, v), traversals in route_edges(route).items():
        if not link_capacity_available(network, u, v, bandwidth * traversals, t1, t2):
            return False
    return True


def route_is_valid(network: Network, route: Sequence[Any], source: Any, destination: Any,
                   servers: Sequence[Any] = ()) -> bool:
    """Check endpoints, graph edges and ordered VNF server visits."""
    if not route or route[0] != source or route[-1] != destination:
        return False
    if any(not network.G.has_edge(u, v) for u, v in zip(route[:-1], route[1:])):
        return False
    cursor = 0
    for server in servers:
        try:
            cursor = route.index(server, cursor) + 1
        except ValueError:
            return False
    return True


def processing_delay(network: Network, route: Sequence[Any], servers: Sequence[Any],
                    vnfs: Sequence[Any], vnf_ids: Sequence[int]) -> float:
    """Return link, server and VNF processing delay for a placement."""
    if len(servers) != len(vnf_ids):
        raise ValueError("one placement server is required for every VNF")
    link_delay = sum(network.G[u][v]["dl"] for u, v in zip(route[:-1], route[1:]))
    server_delay = sum(network.G.nodes[node]["d"] for node in servers)
    vnf_delay = sum(vnfs[vnf_id].df[node] for vnf_id, node in zip(vnf_ids, servers))
    return link_delay + server_delay + vnf_delay


def deadline_available(deadline: float, current_time: float, delay: float) -> bool:
    """Check delay against both absolute and legacy relative deadlines."""
    budget = deadline - current_time if deadline > current_time else deadline
    return budget >= 0 and delay <= budget + 1e-9


class ConstraintChecker:
    """Object-oriented facade for checks used by environment and agents."""

    def __init__(self, network: Network, manager: Any | None = None) -> None:
        self.network = network
        self.manager = manager

    def node(self, node: Any, vnf: Any, t1: int, t2: int) -> bool:
        if self.manager is not None:
            return self.manager.check_deploy_DC(node, vnf, t1, t2)
        return node_capacity_available(self.network, node, vnf, t1, t2)

    def route(self, route: Sequence[Any], bandwidth: float, t1: int, t2: int) -> bool:
        if self.manager is not None:
            for (u, v), traversals in route_edges(route).items():
                if not self.manager.check_deploy_edge(u, v, bandwidth * traversals, t1, t2):
                    return False
            return bool(route)
        return route_capacity_available(self.network, route, bandwidth, t1, t2)


__all__ = [
    "ConstraintChecker", "deadline_available", "link_capacity_available",
    "node_capacity_available", "processing_delay", "route_capacity_available",
    "route_edges", "route_is_valid", "validate_interval",
]
