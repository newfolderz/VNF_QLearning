from dataclasses import dataclass, field
from typing import Any, List

from .network import Network
from .request import SFC, Request
from .vnf import VNF

class LegacyAllocationManager:
    def __init__(self, network: Network, VNFs: list):
        self.network = network
        self.F = VNFs

        # Simulation attributes
        self.time_slot = 0
        
        # KHÔNG CÒN operating và waiting queues nữa!
        # Trạng thái mạng bây giờ hoàn toàn nằm trong các mảng time-series của Network.

    def max_cost(self, requests: List[Request]):
        cost = np.zeros(len(self.F), dtype=float)
        for i, vnf in enumerate(self.F):
            for u in self.network.server_nodes:
                cost_u = 0.0
                for res in ['c', 'r', 'h']:
                    cost_u += self.network.G.nodes[u][f'{res}_cost'] * getattr(vnf, f'{res}f')
                cost[i] = max(cost[i], cost_u)

        total_cost = 0.0
        for req in requests:
            for i in req.Fr:
                total_cost += cost[i]
        return total_cost

    def get_cost(self, sfc: SFC):
        cost = 0.0
        for vnf_id, u in zip(sfc.request.Fr, sfc.F_nodes):
            for res in ['c', 'r', 'h']:
                cost += self.network.G.nodes[u][f'{res}_cost'] * getattr(self.F[vnf_id], f'{res}f')
        return cost

    def get_delay(self, sfc: SFC):
        G = self.network.G

        Dl = 0.0
        for a, b in zip(sfc.route_nodes[:-1], sfc.route_nodes[1:]):
            Dl += G[a][b]['dl']
        Di = 0.0
        Dn = 0.0
        for vnf_id, node in zip(sfc.request.Fr, sfc.F_nodes):
            Di += self.F[vnf_id].df[node]
            Dn += G.nodes[node]['d']

        return Dl + Di + Dn

    # HÀM DEPLOY MỚI: Phóng thẳng tài nguyên vào tương lai!
    def check_deploy_edge(self, u, v, bw: float, t1: int, t2: int):
        """
        Kiểm tra xem có thể deploy băng thông bw trên cạnh (u, v) trong khoảng thời gian [t1, t2] hay không
        """
        for t in range(t1, t2):
            if self.network.G[u][v]['b_use'][t] + bw > self.network.G[u][v]['b_cap'] + 1e-9:
                return False
        return True

    def deploy_edge(self, u, v, bw: float, t1: int, t2: int):
        """
        Chiếm dụng băng thông bw trên cạnh (u, v) trong khoảng thời gian [t1, t2]
        """
        for t in range(t1, t2):
            self.network.G[u][v]['b_use'][t] += bw
            if self.network.G[u][v]['b_use'][t] > self.network.G[u][v]['b_cap'] + 1e-9:
                raise ValueError(f"Bandwidth violation on link ({u}, {v}) at time {t}")

    def check_deploy_DC(self, node, vnf, t1: int, t2: int):
        """
        Kiểm tra xem có thể deploy VNF trên Server node trong khoảng thời gian [t1, t2] hay không
        """
        for t in range(t1, t2):
            if (self.network.G.nodes[node]['c_use'][t] + vnf.cf > self.network.G.nodes[node]['c_cap'] + 1e-9 or
                self.network.G.nodes[node]['r_use'][t] + vnf.rf > self.network.G.nodes[node]['r_cap'] + 1e-9 or
                self.network.G.nodes[node]['h_use'][t] + vnf.hf > self.network.G.nodes[node]['h_cap'] + 1e-9):
                return False
        return True

    def deploy_DC(self, node, vnf, t1: int, t2: int):
        """
        Chiếm dụng CPU, RAM, HDD của vnf trên Server node trong khoảng thời gian [t1, t2]
        """
        for t in range(t1, t2):
            self.network.G.nodes[node]['c_use'][t] += vnf.cf
            self.network.G.nodes[node]['r_use'][t] += vnf.rf
            self.network.G.nodes[node]['h_use'][t] += vnf.hf
            
            # Check violation với dung sai
            if any(self.network.G.nodes[node][f'{res}_use'][t] > self.network.G.nodes[node][f'{res}_cap'] + 1e-9 for res in ['c', 'r', 'h']):
                raise ValueError(f"Resource violation when deploying VNF on node {node} at time {t1}-{t2}")

    def undeploy_DC(self, node, vnf, t1: int, t2: int):
        """
        Giải phóng CPU, RAM, HDD của vnf trên Server node trong khoảng thời gian [t1, t2]
        """
        for t in range(t1, t2):
            self.network.G.nodes[node]['c_use'][t] -= vnf.cf
            self.network.G.nodes[node]['r_use'][t] -= vnf.rf
            self.network.G.nodes[node]['h_use'][t] -= vnf.hf
            
            # Chống underflow ảo bằng -1e-9
            if any(self.network.G.nodes[node][f'{res}_use'][t] < -1e-9 for res in ['c', 'r', 'h']):
                raise ValueError(f"Resource underflow when undeploying VNF on node {node} at time {t1}-{t2}")
            
            # Dọn rác (đưa số ảo xấp xỉ 0 về 0.0 tuyệt đối)
            for res in ['c', 'r', 'h']:
                if abs(self.network.G.nodes[node][f'{res}_use'][t]) < 1e-9:
                    self.network.G.nodes[node][f'{res}_use'][t] = 0.0
            
    def undeploy_edge(self, u, v, bw: float, t1: int, t2: int):
        """
        Giải phóng băng thông bw trên cạnh (u, v) trong khoảng thời gian [t1, t2]
        """
        for t in range(t1, t2):
            self.network.G[u][v]['b_use'][t] -= bw
            
            # Chống underflow ảo
            if self.network.G[u][v]['b_use'][t] < -1e-9:
                raise ValueError(f"Bandwidth underflow on link ({u}, {v}) at time {t}")
            
            # Dọn rác
            if abs(self.network.G[u][v]['b_use'][t]) < 1e-9:
                self.network.G[u][v]['b_use'][t] = 0.0
    def advance(self):
        self.time_slot += 1
        self.network.advance_time()  # Đẩy băng chuyền time-series đi 1 slot
class AllocationRecord:
    pass 


@dataclass(slots=True)
class NodeAllocation:
    """One VNF occupying one server during ``[t1, t2)``."""

    node: Any
    vnf: VNF
    t1: int
    t2: int


@dataclass(slots=True)
class EdgeAllocation:
    """One bandwidth reservation occupying one link during ``[t1, t2)``."""

    u: Any
    v: Any
    bandwidth: float
    t1: int
    t2: int


@dataclass(slots=True)
class AllocationRecord:
    """Bookkeeping for one accepted service function chain."""

    request: Request
    sfc: SFC
    start_time: int
    end_time: int
    accepted: bool = True
    node_allocations: list[NodeAllocation] = field(default_factory=list)
    edge_allocations: list[EdgeAllocation] = field(default_factory=list)


class AllocationManager:
    """Validate, apply and release reservations on a :class:`Network`."""

    _EPSILON = 1e-9

    def __init__(self, network: Network, vnfs: list[VNF]) -> None:
        self.network = network
        self.F = vnfs
        self.time_slot = 0
        self.active_allocations: dict[int, AllocationRecord] = {}

    def _validate_interval(self, t1: int, t2: int) -> None:
        if t1 < 0 or t2 <= t1 or t2 > self.network.max_horizon:
            raise ValueError(
                f"Invalid interval [{t1}, {t2}); expected 0 <= t1 < t2 "
                f"<= {self.network.max_horizon}"
            )

    def _vnf(self, vnf_id: int) -> VNF:
        try:
            return self.F[vnf_id]
        except IndexError as exc:
            raise ValueError(f"Unknown VNF id: {vnf_id}") from exc

    def max_cost(self, requests: list[Request]) -> float:
        """Return the maximum placement cost for the supplied requests."""

        max_cost_by_vnf: list[float] = []
        for vnf in self.F:
            max_cost_by_vnf.append(
                max(
                    (
                        sum(
                            self.network.G.nodes[node][f"{resource}_cost"]
                            * getattr(vnf, f"{resource}f")
                            for resource in ("c", "r", "h")
                        )
                        for node in self.network.server_nodes
                    ),
                    default=0.0,
                )
            )
        return sum(
            max_cost_by_vnf[vnf_id]
            for request in requests
            for vnf_id in request.Fr
        )

    def get_cost(self, sfc: SFC) -> float:
        """Return CPU/RAM/HDD placement cost for an SFC."""

        if len(sfc.request.Fr) != len(sfc.F_nodes):
            raise ValueError("VNF ids and placement nodes must have the same length")
        return sum(
            sum(
                self.network.G.nodes[node][f"{resource}_cost"]
                * getattr(self._vnf(vnf_id), f"{resource}f")
                for resource in ("c", "r", "h")
            )
            for vnf_id, node in zip(sfc.request.Fr, sfc.F_nodes)
        )

    def get_delay(self, sfc: SFC) -> float:
        """Return link, VNF-processing and server delay for an SFC."""

        if len(sfc.request.Fr) != len(sfc.F_nodes):
            raise ValueError("VNF ids and placement nodes must have the same length")
        graph = self.network.G
        link_delay = sum(
            graph[u][v]["dl"] for u, v in zip(sfc.route_nodes[:-1], sfc.route_nodes[1:])
        )
        processing_delay = sum(
            self._vnf(vnf_id).df[node]
            for vnf_id, node in zip(sfc.request.Fr, sfc.F_nodes)
        )
        server_delay = sum(graph.nodes[node]["d"] for node in sfc.F_nodes)
        return link_delay + processing_delay + server_delay

    def check_deploy_edge(
        self, u: Any, v: Any, bandwidth: float, t1: int, t2: int
    ) -> bool:
        """Check link capacity during the half-open interval ``[t1, t2)``."""

        self._validate_interval(t1, t2)
        if bandwidth < 0:
            raise ValueError("Bandwidth must be non-negative")
        edge = self.network.G[u][v]
        return all(
            edge["b_use"][t] + bandwidth <= edge["b_cap"] + self._EPSILON
            for t in range(t1, t2)
        )

    def deploy_edge(
        self, u: Any, v: Any, bandwidth: float, t1: int, t2: int
    ) -> None:
        """Reserve link bandwidth during ``[t1, t2)``."""

        if not self.check_deploy_edge(u, v, bandwidth, t1, t2):
            raise ValueError(f"Bandwidth capacity exceeded on link ({u}, {v})")
        usage = self.network.G[u][v]["b_use"]
        for t in range(t1, t2):
            usage[t] += bandwidth

    def check_deploy_DC(
        self, node: Any, vnf: VNF, t1: int, t2: int
    ) -> bool:
        """Check CPU, RAM and HDD capacity during ``[t1, t2)``."""

        self._validate_interval(t1, t2)
        server = self.network.G.nodes[node]
        return all(
            server["c_use"][t] + vnf.cf <= server["c_cap"] + self._EPSILON
            and server["r_use"][t] + vnf.rf <= server["r_cap"] + self._EPSILON
            and server["h_use"][t] + vnf.hf <= server["h_cap"] + self._EPSILON
            for t in range(t1, t2)
        )

    def deploy_DC(self, node: Any, vnf: VNF, t1: int, t2: int) -> None:
        """Reserve server resources during ``[t1, t2)``."""

        if not self.check_deploy_DC(node, vnf, t1, t2):
            raise ValueError(f"Server capacity exceeded on node {node}")
        server = self.network.G.nodes[node]
        for t in range(t1, t2):
            server["c_use"][t] += vnf.cf
            server["r_use"][t] += vnf.rf
            server["h_use"][t] += vnf.hf

    def undeploy_DC(self, node: Any, vnf: VNF, t1: int, t2: int) -> None:
        """Release server resources previously reserved during ``[t1, t2)``."""

        self._validate_interval(t1, t2)
        server = self.network.G.nodes[node]
        for t in range(t1, t2):
            if any(
                server[f"{resource}_use"][t] - getattr(vnf, f"{resource}f")
                < -self._EPSILON
                for resource in ("c", "r", "h")
            ):
                raise ValueError(f"Resource underflow when releasing node {node}")
        for t in range(t1, t2):
            for resource in ("c", "r", "h"):
                usage_key = f"{resource}_use"
                server[usage_key][t] -= getattr(vnf, f"{resource}f")
                if abs(server[usage_key][t]) < self._EPSILON:
                    server[usage_key][t] = 0.0

    def undeploy_edge(
        self, u: Any, v: Any, bandwidth: float, t1: int, t2: int
    ) -> None:
        """Release link bandwidth previously reserved during ``[t1, t2)``."""

        self._validate_interval(t1, t2)
        usage = self.network.G[u][v]["b_use"]
        if any(usage[t] - bandwidth < -self._EPSILON for t in range(t1, t2)):
            raise ValueError(f"Bandwidth underflow when releasing link ({u}, {v})")
        for t in range(t1, t2):
            usage[t] -= bandwidth
            if abs(usage[t]) < self._EPSILON:
                usage[t] = 0.0

    def register(self, record: AllocationRecord) -> None:
        """Register an already-applied allocation by request id."""

        request_id = record.request.idx
        if request_id in self.active_allocations:
            raise ValueError(f"Request {request_id} already has an allocation")
        self.active_allocations[request_id] = record

    def release(self, record: AllocationRecord) -> None:
        """Release every reservation stored in an allocation record."""

        for allocation in reversed(record.edge_allocations):
            self.undeploy_edge(
                allocation.u, allocation.v, allocation.bandwidth,
                allocation.t1, allocation.t2,
            )
        for allocation in reversed(record.node_allocations):
            self.undeploy_DC(
                allocation.node, allocation.vnf, allocation.t1, allocation.t2,
            )
        self.active_allocations.pop(record.request.idx, None)

    def advance(self) -> None:
        """Advance the simulation by one time slot."""

        self.time_slot += 1
        self.network.advance_time()
