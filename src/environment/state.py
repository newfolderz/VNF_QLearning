"""State construction and normalization for :mod:`network_env`.

The domain objects keep resource values in the network itself.  This module
only creates an agent-facing view, so encoding a state never mutates the
simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

try:
    from ..domain.network import Network
except ImportError:  # pragma: no cover
    from domain.network import Network


@dataclass(frozen=True, slots=True)
class StateLayout:
    """Stable ordering used when converting a state to a flat vector."""

    nodes: tuple[Any, ...]
    edges: tuple[tuple[Any, Any], ...]
    max_pending: int = 1


class StateEncoder:
    """Build raw and normalized states from a ``NetworkEnv`` observation."""

    def __init__(
        self,
        network: Network,
        *,
        node_order: Sequence[Any] | None = None,
        max_pending: int = 1,
    ) -> None:
        if not isinstance(network, Network):
            raise TypeError("network must be a domain.network.Network")
        if max_pending < 1:
            raise ValueError("max_pending must be positive")
        nodes = tuple(node_order or network.server_nodes)
        if any(node not in network.server_nodes for node in nodes):
            raise ValueError("node_order must contain only server nodes")
        edges = tuple(network.G.edges)
        self.network = network
        self.layout = StateLayout(nodes, edges, max_pending)

    def from_env(self, env: Any) -> dict[str, Any]:
        """Return the raw state exposed by ``NetworkEnv``."""
        if not hasattr(env, "_observation"):
            raise TypeError("env must expose _observation()")
        return env._observation()

    def normalize(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Normalize capacities to approximately ``[0, 1]``.

        Missing nodes/links are represented by zero.  Request attributes are
        kept as semantic values in the mapping and separately encoded in the
        flat vector, which avoids losing request ids or node labels.
        """
        node_resources: dict[Any, dict[str, float]] = {}
        raw_nodes = state.get("node_resources", {})
        for node in self.layout.nodes:
            data = raw_nodes.get(node, {})
            capacity = self.network.G.nodes[node]
            node_resources[node] = {
                resource: self._ratio(data.get(resource, 0.0), capacity[f"{key}_cap"])
                for resource, key in (("cpu", "c"), ("ram", "r"), ("hdd", "h"))
            }

        link_bandwidth: dict[tuple[Any, Any], float] = {}
        raw_links = state.get("link_bandwidth", {})
        for u, v in self.layout.edges:
            value = raw_links.get((u, v), raw_links.get((v, u), 0.0))
            link_bandwidth[(u, v)] = self._ratio(value, self.network.G[u][v]["b_cap"])

        return {
            "time": float(state.get("time", 0)),
            "node_resources": node_resources,
            "link_bandwidth": link_bandwidth,
            "current_request": state.get("current_request"),
            "pending_requests": list(state.get("pending_requests", [])),
            "active_requests": list(state.get("active_requests", [])),
            "vnf_placed": dict(state.get("vnf_placed", {})),
        }

    @staticmethod
    def _ratio(value: Any, capacity: Any) -> float:
        try:
            if float(capacity) <= 0:
                return 0.0
            return max(0.0, min(1.0, float(value) / float(capacity)))
        except (TypeError, ValueError):
            return 0.0

    def vector(self, state: Mapping[str, Any], *, normalized: bool = True) -> list[float]:
        """Return a deterministic flat vector suitable for a neural agent."""
        source = self.normalize(state) if normalized else state
        values: list[float] = [float(source.get("time", 0.0))]
        for node in self.layout.nodes:
            resources = source.get("node_resources", {}).get(node, {})
            values.extend(float(resources.get(key, 0.0)) for key in ("cpu", "ram", "hdd"))
        placements = source.get("vnf_placed", {})
        active_count = max(1, len(source.get("active_requests", [])))
        placement_counts = {node: 0 for node in self.layout.nodes}
        for servers in placements.values():
            for node in servers:
                if node in placement_counts:
                    placement_counts[node] += 1
        values.extend(placement_counts[node] / active_count for node in self.layout.nodes)
        for edge in self.layout.edges:
            values.append(float(source.get("link_bandwidth", {}).get(edge, 0.0)))

        pending = list(source.get("pending_requests", []))[: self.layout.max_pending]
        for request in pending:
            values.extend(self._request_vector(request))
        values.extend([0.0] * (self.layout.max_pending - len(pending)) * 6)
        return values

    @staticmethod
    def _request_vector(request: Mapping[str, Any] | None) -> list[float]:
        if not request:
            return [0.0] * 6
        chain = request.get("vnf_chain", [])
        return [
            float(request.get("id", 0)),
            float(request.get("arrival", 0)),
            float(request.get("source", 0)) if isinstance(request.get("source", 0), (int, float)) else 0.0,
            float(request.get("destination", 0)) if isinstance(request.get("destination", 0), (int, float)) else 0.0,
            float(request.get("bandwidth", 0.0)),
            float(len(chain)),
        ]

    def encode(self, env: Any) -> dict[str, Any]:
        """Return ``raw``, ``normalized`` and ``vector`` in one object."""
        raw = self.from_env(env)
        normalized = self.normalize(raw)
        return {"raw": raw, "normalized": normalized, "vector": self.vector(normalized, normalized=False)}


def build_state(env: Any, *, encoder: StateEncoder | None = None) -> dict[str, Any]:
    """Convenience function returning the normalized agent state."""
    if encoder is None:
        encoder = StateEncoder(env.network)
    return encoder.normalize(encoder.from_env(env))


__all__ = ["StateLayout", "StateEncoder", "build_state"]
