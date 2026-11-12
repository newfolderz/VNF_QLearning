"""State transitions for accepting and advancing service requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

try:
    from ..domain.allocation import AllocationManager, AllocationRecord, EdgeAllocation, NodeAllocation
    from ..domain.network import Network
    from ..domain.request import Request, SFC
    from .constraints import ConstraintChecker, deadline_available, processing_delay, route_is_valid
except ImportError:  # pragma: no cover
    from domain.allocation import AllocationManager, AllocationRecord, EdgeAllocation, NodeAllocation
    from domain.network import Network
    from domain.request import Request, SFC
    from environment.constraints import ConstraintChecker, deadline_available, processing_delay, route_is_valid


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Result of one accepted transition."""

    record: AllocationRecord
    cost: float
    delay: float
    duration: int


class TransitionEngine:
    """Validate, apply, register and advance network allocations."""

    def __init__(self, network: Network, vnfs: Sequence[Any],
                 manager: AllocationManager | None = None) -> None:
        self.network = network
        self.vnfs = list(vnfs)
        self.manager = manager or AllocationManager(network, self.vnfs)

    def apply(self, request: Request, servers: Sequence[Any], route: Sequence[Any],
              *, current_time: int = 0, duration: int = 1) -> TransitionResult:
        """Atomically reserve node and link resources for one request."""
        if duration < 1 or duration > self.network.max_horizon:
            raise ValueError("duration must fit in network.max_horizon")
        if len(servers) != len(request.Fr):
            raise ValueError("one placement server is required for every VNF")
        if not route_is_valid(self.network, route, request.st, request.d, servers):
            raise ValueError("route must connect endpoints and visit servers in VNF order")
        if any(server not in self.network.server_nodes for server in servers):
            raise ValueError("all VNF placements must be server nodes")

        candidate = SFC(request, current_time)
        candidate.F_nodes = list(servers)
        candidate.route_nodes = list(route)
        delay = processing_delay(self.network, route, servers, self.vnfs, request.Fr)
        if not deadline_available(float(request.dr), current_time, delay):
            raise ValueError(f"end-to-end delay {delay:g} exceeds deadline budget")

        checker = ConstraintChecker(self.network, self.manager)
        for vnf_id, server in zip(request.Fr, servers):
            if not checker.node(server, self.vnfs[vnf_id], 0, duration):
                raise ValueError(f"insufficient server capacity on node {server}")
        if not checker.route(route, float(request.br), 0, duration):
            raise ValueError("insufficient bandwidth on route")

        node_allocations = [
            NodeAllocation(server, self.vnfs[vnf_id], 0, duration)
            for vnf_id, server in zip(request.Fr, servers)
        ]
        edge_allocations = [
            EdgeAllocation(u, v, float(request.br), 0, duration)
            for u, v in zip(route[:-1], route[1:])
        ]
        applied_nodes: list[NodeAllocation] = []
        applied_edges: list[EdgeAllocation] = []
        try:
            for allocation in node_allocations:
                self.manager.deploy_DC(allocation.node, allocation.vnf, allocation.t1, allocation.t2)
                applied_nodes.append(allocation)
            for allocation in edge_allocations:
                self.manager.deploy_edge(
                    allocation.u, allocation.v, allocation.bandwidth,
                    allocation.t1, allocation.t2,
                )
                applied_edges.append(allocation)
        except Exception:
            for allocation in reversed(applied_edges):
                self.manager.undeploy_edge(
                    allocation.u, allocation.v, allocation.bandwidth,
                    allocation.t1, allocation.t2,
                )
            for allocation in reversed(applied_nodes):
                self.manager.undeploy_DC(
                    allocation.node, allocation.vnf, allocation.t1, allocation.t2,
                )
            raise

        record = AllocationRecord(
            request=request,
            sfc=candidate,
            start_time=current_time,
            end_time=current_time + duration,
            node_allocations=node_allocations,
            edge_allocations=edge_allocations,
        )
        self.manager.register(record)
        return TransitionResult(record, self.manager.get_cost(candidate), delay, duration)

    def release(self, record: AllocationRecord) -> None:
        """Release a record before its local reservation window is advanced."""
        self.manager.release(record)

    def advance(self) -> None:
        """Advance the sliding resource window by one time-slot."""
        self.manager.advance()

    def expire(self, records: dict[int, AllocationRecord], current_time: int) -> dict[int, AllocationRecord]:
        """Drop expired bookkeeping after the network window has advanced."""
        active = {rid: record for rid, record in records.items() if record.end_time > current_time}
        self.manager.active_allocations = {
            rid: record for rid, record in self.manager.active_allocations.items()
            if record.end_time > current_time
        }
        return active


__all__ = ["TransitionEngine", "TransitionResult"]
