"""Action representation and candidate generation for VNF placement/routing."""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import networkx as nx

try:
    from ..domain.network import Network
    from ..domain.request import Request
except ImportError:  # pragma: no cover
    from domain.network import Network
    from domain.request import Request


@dataclass(frozen=True, slots=True)
class Action:
    """A complete placement and route decision for one request."""

    servers: tuple[Any, ...]
    route: tuple[Any, ...] = ()
    request_id: int | None = None

    def __init__(self, servers: Iterable[Any], route: Iterable[Any] = (), request_id: int | None = None) -> None:
        object.__setattr__(self, "servers", tuple(servers))
        object.__setattr__(self, "route", tuple(route))
        object.__setattr__(self, "request_id", request_id)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"servers": list(self.servers), "route": list(self.route)}
        if self.request_id is not None:
            result["request_id"] = self.request_id
        return result

    @classmethod
    def from_any(cls, action: Any) -> "Action":
        if isinstance(action, cls):
            return action
        if isinstance(action, Mapping):
            return cls(action.get("servers", action.get("placements", [])),
                       action.get("route", action.get("route_nodes", [])),
                       action.get("request_id"))
        if isinstance(action, (tuple, list)) and len(action) == 2:
            return cls(action[0], action[1])
        raise TypeError("action must be Action, mapping, or a (servers, route) pair")


class ActionSpace:
    """Generate structurally valid placement/route actions.

    Capacity and deadline feasibility remain the responsibility of
    ``NetworkEnv`` because they depend on the current time-slot state.
    """

    def __init__(self, network: Network, *, max_combinations: int = 10_000,
                 manager: Any | None = None) -> None:
        if not isinstance(network, Network):
            raise TypeError("network must be a domain.network.Network")
        self.network = network
        self.max_combinations = max_combinations
        self.manager = manager

    def candidate_servers(
        self,
        request: Request,
        vnf_catalog: Sequence[Any] | None = None,
        *,
        manager: Any | None = None,
        t1: int = 0,
        t2: int = 1,
    ) -> list[list[Any]]:
        """Return servers compatible with each VNF.

        Static capacity and processing-delay checks are always performed.  If
        an :class:`AllocationManager` is supplied, current reservations are
        also checked over ``[t1, t2)``.  The latter is optional to preserve the
        old use of this method for constructing a static action space.
        """
        if t1 < 0 or t2 <= t1:
            raise ValueError("expected 0 <= t1 < t2")
        candidates: list[list[Any]] = []
        for vnf_id in request.Fr:
            options = []
            vnf = None if vnf_catalog is None else vnf_catalog[vnf_id]
            for node in self.network.server_nodes:
                if vnf is not None:
                    delay = vnf.df.get(node, float("inf"))
                    if not (delay < float("inf")):
                        continue
                    if not (
                        vnf.cf <= self.network.G.nodes[node]["c_cap"]
                        and vnf.rf <= self.network.G.nodes[node]["r_cap"]
                        and vnf.hf <= self.network.G.nodes[node]["h_cap"]
                    ):
                        continue
                    if manager is not None and not manager.check_deploy_DC(
                        node, vnf, t1, t2
                    ):
                        continue
                options.append(node)
            candidates.append(options)
        return candidates

    def feasible_servers(
        self,
        request: Request,
        vnf_catalog: Sequence[Any],
        manager: Any | None = None,
        *,
        t1: int = 0,
        t2: int = 1,
    ) -> list[list[Any]]:
        """Return candidates that also fit current time-slot reservations."""
        resource_manager = manager if manager is not None else self.manager
        if resource_manager is None:
            raise ValueError("feasible_servers requires an AllocationManager")
        return self.candidate_servers(
            request, vnf_catalog, manager=resource_manager, t1=t1, t2=t2
        )

    def route(self, request: Request, servers: Sequence[Any]) -> list[Any]:
        if len(servers) != len(request.Fr):
            raise ValueError("one placement server is required for every VNF")
        points = [request.st, *servers, request.d]
        result: list[Any] = []
        for source, target in zip(points[:-1], points[1:]):
            segment = nx.shortest_path(self.network.G, source, target, weight="dl")
            result.extend(segment if not result else segment[1:])
        return result

    def validate(self, request: Request, action: Action) -> None:
        if len(action.servers) != len(request.Fr):
            raise ValueError("one placement server is required for every VNF")
        if not action.route:
            return
        if action.route[0] != request.st or action.route[-1] != request.d:
            raise ValueError("route must start at request.st and end at request.d")
        cursor = 0
        for server in action.servers:
            try:
                cursor = action.route.index(server, cursor) + 1
            except ValueError as exc:
                raise ValueError("route must visit servers in VNF order") from exc
        if any(not self.network.G.has_edge(u, v) for u, v in zip(action.route[:-1], action.route[1:])):
            raise ValueError("route contains an unknown network edge")

    def enumerate(self, request: Request, vnf_catalog: Sequence[Any] | None = None,
                  *, manager: Any | None = None, t1: int = 0, t2: int = 1) -> list[Action]:
        manager = self.manager if manager is None else manager
        candidates = self.candidate_servers(
            request, vnf_catalog, manager=manager, t1=t1, t2=t2
        )
        count = 1
        for options in candidates:
            count *= len(options)
        if count > self.max_combinations:
            raise ValueError("placement action space exceeds max_combinations")
        return [Action(servers, self.route(request, servers), request.idx)
                for servers in itertools.product(*candidates)]

    def sample(self, request: Request, vnf_catalog: Sequence[Any] | None = None,
               rng: random.Random | None = None, *, manager: Any | None = None,
               t1: int = 0, t2: int = 1) -> Action:
        rng = rng or random.Random()
        manager = self.manager if manager is None else manager
        candidates = self.candidate_servers(
            request, vnf_catalog, manager=manager, t1=t1, t2=t2
        )
        if any(not options for options in candidates):
            raise ValueError("at least one VNF has no candidate server")
        servers = [rng.choice(options) for options in candidates]
        return Action(servers, self.route(request, servers), request.idx)


__all__ = ["Action", "ActionSpace"]
