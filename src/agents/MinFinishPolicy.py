"""Placement policies that do not learn."""

from __future__ import annotations

from typing import Any

import networkx as nx

from ..environment.action import Action, ActionSpace
from ..environment.constraints import route_is_valid


class MinFinishPolicy:
    """Place each VNF on the DC where that VNF finishes earliest.

    For VNF ``i``, the finish time is estimated as::

        previous_finish + network_delay + server_delay + vnf_processing_delay

    The policy makes the decision from left to right along the VNF chain.  It
    uses the environment's current resource reservations when constructing
    candidates, but it does not update resources itself; ``env.step`` remains
    the single owner of state transitions.
    """

    def __init__(self, action_space: ActionSpace) -> None:
        self.action_space = action_space

    def choose(self, env: Any) -> Action | None:
        request = env.current_request
        if request is None:
            return None

        duration = env._duration(request)
        candidates = self.action_space.candidate_servers(
            request,
            env.vnfs,
            manager=env.manager,
            t1=0,
            t2=duration,
        )
        if any(not options for options in candidates):
            return None

        servers: list[Any] = []
        route: list[Any] = []
        previous = request.st
        finish_time = float(env.time)

        for vnf_id, options in zip(request.Fr, candidates):
            ranked: list[tuple[float, str, Any, list[Any]]] = []
            for server in options:
                try:
                    segment = nx.shortest_path(
                        self.action_space.network.G,
                        previous,
                        server,
                        weight="dl",
                    )
                except nx.NetworkXNoPath:
                    continue

                network_delay = sum(
                    self.action_space.network.G[u][v]["dl"]
                    for u, v in zip(segment[:-1], segment[1:])
                )
                node_delay = self.action_space.network.G.nodes[server]["d"]
                vnf_delay = env.vnfs[vnf_id].df[server]
                candidate_finish = finish_time + network_delay + node_delay + vnf_delay
                ranked.append((candidate_finish, repr(server), server, segment))

            if not ranked:
                return None

            candidate_finish, _, server, segment = min(ranked)
            finish_time = candidate_finish
            servers.append(server)
            route.extend(segment if not route else segment[1:])
            previous = server

        try:
            destination_segment = nx.shortest_path(
                self.action_space.network.G,
                previous,
                request.d,
                weight="dl",
            )
        except nx.NetworkXNoPath:
            return None
        route.extend(destination_segment if not route else destination_segment[1:])

        action = Action(servers, route, request.idx)
        if not route_is_valid(self.action_space.network, route, request.st, request.d, servers):
            return None
        return action


__all__ = ["MinFinishPolicy"]
