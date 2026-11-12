"""Time-slotted environment for VNF placement and routing.

The environment deliberately has no dependency on Gym/Gymnasium.  This keeps
the domain model usable by the baseline algorithms as well as by RL agents.
``step`` follows the familiar ``(observation, reward, terminated, truncated,
info)`` convention.
"""

from __future__ import annotations

from collections import defaultdict
from math import ceil
from typing import Any, Iterable, Mapping, Sequence

import networkx as nx

try:  # Works both as ``src.environment`` and with ``src`` on PYTHONPATH.
    from .action import Action
    from .constraints import ConstraintChecker, route_is_valid
    from .reward import RewardCalculator, RewardTracker
    from .routing import shortest_route
    from .transition import TransitionEngine
    from ..domain.allocation import AllocationManager, AllocationRecord, EdgeAllocation, NodeAllocation
    from ..domain.network import Network
    from ..domain.request import Request, SFC
except ImportError:  # pragma: no cover - import style depends on the caller.
    from environment.action import Action
    from environment.constraints import ConstraintChecker, route_is_valid
    from environment.reward import RewardCalculator, RewardTracker
    from environment.routing import shortest_route
    from environment.transition import TransitionEngine
    from domain.allocation import AllocationManager, AllocationRecord, EdgeAllocation, NodeAllocation
    from domain.network import Network
    from domain.request import Request, SFC


class NetworkEnv:
    """Place one pending request per call while the network advances in slots.

    Parameters
    ----------
    network:
        A :class:`domain.network.Network` instance.
    vnfs:
        VNF catalogue indexed by the ids in ``Request.Fr``.
    requests:
        Requests, in any order.  They are sorted by arrival time on reset.
    rho:
        Reward for accepting a request.  Placement cost is subtracted from it.
    max_steps:
        Number of simulated slots.  Defaults to the largest request deadline
        (or arrival time) plus one.
    """

    def __init__(
        self,
        network: Network,
        vnfs: Sequence[Any],
        requests: Iterable[Request] | None = None,
        *,
        rho: float = 1.0,
        max_steps: int | None = None,
        seed: int | None = None,
    ) -> None:
        if not isinstance(network, Network):
            raise TypeError("network must be a domain.network.Network")
        self.network = network
        self.vnfs = list(vnfs)
        self.rho = float(rho)
        self._requests = [self._coerce_request(r, i) for i, r in enumerate(requests or [])]
        self.max_steps = max_steps
        self.seed = seed
        self.manager = AllocationManager(network, self.vnfs)
        self.transition = TransitionEngine(network, self.vnfs, self.manager)
        self.reward_calculator = RewardCalculator(self.rho)
        self.reward_tracker = RewardTracker()
        self._reset_state()

    @staticmethod
    def _coerce_request(request: Request | Mapping[str, Any], fallback_id: int) -> Request:
        if isinstance(request, Request):
            return request
        if not isinstance(request, Mapping):
            raise TypeError("requests must contain Request objects or mappings")
        return Request(
            request.get("id", fallback_id),
            request.get("arrival_time", request.get("arrival", 0)),
            request.get("source", request.get("start")),
            request.get("destination", request.get("dest")),
            list(request.get("vnf_chain", request.get("Fr", []))),
            request.get("bandwidth", request.get("br", 0.0)),
            request.get("deadline", request.get("dr", 1.0)),
            start_time=request.get("start_time", request.get("start_at")),
        )

    def _reset_state(self) -> None:
        self.time = 0
        self._processed: set[int] = set()
        self._pending: list[Request] = []
        self._records: dict[int, AllocationRecord] = {}
        self._last_info: dict[str, Any] = {}

    def reset(
        self,
        *,
        requests: Iterable[Request] | None = None,
        seed: int | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Restore resource usage and return the initial observation."""
        del options
        if requests is not None:
            self._requests = [self._coerce_request(r, i) for i, r in enumerate(requests)]
        if seed is not None:
            self.seed = seed
        self._clear_network_usage()
        self.manager = AllocationManager(self.network, self.vnfs)
        self.transition = TransitionEngine(self.network, self.vnfs, self.manager)
        self.reward_tracker.reset()
        self._reset_state()
        self._add_arrivals()
        return self._observation()

    def _clear_network_usage(self) -> None:
        for node in self.network.server_nodes:
            for resource in ("c", "r", "h"):
                self.network.G.nodes[node][f"{resource}_use"][:] = [
                    0.0
                ] * self.network.max_horizon
        for u, v in self.network.G.edges:
            self.network.G[u][v]["b_use"][:] = [0.0] * self.network.max_horizon

    def _add_arrivals(self) -> None:
        for request in self._requests:
            if request.idx not in self._processed and request.idx not in {r.idx for r in self._pending}:
                if float(request.arrival) <= self.time:
                    self._pending.append(request)
        self._pending.sort(key=lambda request: (request.arrival, request.idx))

    @property
    def current_request(self) -> Request | None:
        return self._pending[0] if self._pending else None

    def _duration(self, request: Request) -> int:
        deadline = float(request.dr)
        # Dataset requests use an absolute deadline; legacy requests use a
        # duration.  Both representations are supported here.
        duration = deadline - self.time if deadline > self.time else deadline
        return max(1, min(self.network.max_horizon, int(ceil(duration))))

    def _deadline_budget(self, request: Request) -> float:
        deadline = float(request.dr)
        return deadline - self.time if deadline > self.time else deadline

    def _route_via_servers(self, request: Request, servers: Sequence[Any]) -> list[Any]:
        return shortest_route(self.network, request, servers)

    def _parse_action(self, action: Any, request: Request) -> tuple[list[Any], list[Any]]:
        if action is None:
            return [], []
        if isinstance(action, Action):
            if action.request_id is not None and action.request_id != request.idx:
                raise ValueError(f"Action targets request {action.request_id}, expected {request.idx}")
            servers, route = list(action.servers), list(action.route)
            if not route:
                route = self._route_via_servers(request, servers)
            return servers, route
        if isinstance(action, Mapping) and "request_id" in action and action["request_id"] != request.idx:
            raise ValueError(f"Action targets request {action['request_id']}, expected {request.idx}")
        if isinstance(action, Mapping):
            servers = list(action.get("servers", action.get("placements", [])))
            route = list(action.get("route", action.get("route_nodes", [])))
        elif isinstance(action, (tuple, list)) and len(action) == 2:
            servers, route = list(action[0]), list(action[1])
        else:
            raise TypeError("action must be a mapping or a (servers, route) pair")
        if not route:
            route = self._route_via_servers(request, servers)
        return servers, route

    def _validate_action(self, request: Request, servers: Sequence[Any], route: Sequence[Any]) -> None:
        if len(servers) != len(request.Fr):
            raise ValueError("one placement server is required for every VNF")
        if not route_is_valid(self.network, route, request.st, request.d, servers):
            raise ValueError("route must connect source/destination and visit servers in VNF order")

    def _check_capacity(self, request: Request, servers: Sequence[Any], route: Sequence[Any], duration: int) -> None:
        if any(server not in self.network.server_nodes for server in servers):
            raise ValueError("all VNF placements must be server nodes")
        checker = ConstraintChecker(self.network, self.manager)
        for vnf_id, server in zip(request.Fr, servers):
            vnf = self.manager.F[vnf_id]
            if not checker.node(server, vnf, 0, duration):
                raise ValueError(f"insufficient server capacity on node {server}")
        if not checker.route(route, float(request.br), 0, duration):
            raise ValueError("insufficient bandwidth on route")

    def _accept(self, request: Request, servers: Sequence[Any], route: Sequence[Any]) -> tuple[float, float, int]:
        duration = self._duration(request)
        result = self.transition.apply(
            request, servers, route, current_time=self.time, duration=duration
        )
        self._records[request.idx] = result.record
        return result.cost, result.delay, result.duration

    def step(self, action: Any = None) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        """Apply an action to the oldest pending request and advance one slot."""
        if self.time >= self._limit():
            raise RuntimeError("episode has ended; call reset()")
        request = self.current_request
        info: dict[str, Any] = {"time": self.time, "request_id": None, "accepted": False}
        reward = 0.0
        if request is not None:
            self._pending.pop(0)
            self._processed.add(request.idx)
            info["request_id"] = request.idx
            try:
                servers, route = self._parse_action(action, request)
                cost, delay, duration = self._accept(request, servers, route)
                reward_result = self.reward_calculator.breakdown(True, cost=cost)
                reward = reward_result.reward
                self.reward_tracker.update(reward_result, cost=cost)
                info.update(accepted=True, cost=cost, delay=delay, duration=duration,
                            servers=list(servers), route=list(route),
                            reward_components={
                                "reward": reward_result.reward,
                                "accepted": reward_result.accepted,
                                "acceptance_component": reward_result.acceptance_component,
                                "cost_component": reward_result.cost_component,
                            })
            except (KeyError, IndexError, nx.NetworkXException, TypeError, ValueError) as exc:
                info["reason"] = str(exc)
                reward_result = self.reward_calculator.breakdown(False)
                reward = reward_result.reward
                self.reward_tracker.update(reward_result)
        self.time += 1
        self.transition.advance()
        self._records = self.transition.expire(self._records, self.time)
        self._add_arrivals()
        terminated = self.time >= self._limit()
        truncated = False
        self._last_info = info
        return self._observation(), reward, terminated, truncated, info

    def _limit(self) -> int:
        if self.max_steps is not None:
            return int(self.max_steps)
        values = [float(r.arrival) for r in self._requests]
        values.extend(float(r.dr) for r in self._requests)
        return max(1, int(ceil(max(values, default=0.0))) + 1)

    def _observation(self) -> dict[str, Any]:
        nodes = {}
        for node in self.network.G.nodes:
            data = self.network.G.nodes[node]
            if data.get("server", False):
                nodes[node] = {"cpu": self.network.remaining_cpu(node),
                               "ram": self.network.remaining_ram(node),
                               "hdd": self.network.remaining_hdd(node)}
        links = {}
        for u, v in self.network.G.edges:
            links[(u, v)] = self.network.remaining_bandwidth(u, v)
        return {
            "time": self.time,
            "node_resources": nodes,
            "link_bandwidth": links,
            "current_request": self._request_summary(self.current_request),
            "pending_requests": [self._request_summary(r) for r in self._pending],
            "active_requests": sorted(self._records),
            "vnf_placed": {rid: list(record.sfc.F_nodes) for rid, record in self._records.items()},
        }

    @staticmethod
    def _request_summary(request: Request | None) -> dict[str, Any] | None:
        if request is None:
            return None
        return {"id": request.idx, "arrival": request.arrival, "source": request.st,
                "destination": request.d, "vnf_chain": list(request.Fr),
                "bandwidth": request.br, "deadline": request.dr}

    def state(self) -> dict[str, Any]:
        """Alias used by baseline agents that call the environment state."""
        return self._observation()


NetworkEnvironment = NetworkEnv

__all__ = ["NetworkEnv", "NetworkEnvironment"]
