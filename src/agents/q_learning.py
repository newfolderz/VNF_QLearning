"""Bounded tabular Q-learning for the placement environment.

This module intentionally does not use a replay buffer or a neural network.
The Q-table is sparse and bounded: only visited state/action pairs are kept.
"""

from __future__ import annotations

from collections import OrderedDict
import itertools
import random
from typing import Any, Hashable

import networkx as nx

from ..environment.action import Action, ActionSpace
from ..environment.state import StateEncoder
from .base import BaseAgent
from .MinFinishPolicy import MinFinishPolicy


StateKey = tuple[Hashable, ...]
ActionKey = tuple[Hashable, ...]


class QLearningAgent(BaseAgent):
    """Sparse tabular Q-learning agent with a bounded action/state view.

    ``NetworkEnv`` exposes a continuous and potentially large state.  This
    agent therefore quantizes resource ratios into ``state_bins`` buckets.
    Actions are complete VNF placements, represented by their server tuple;
    routes are reconstructed from the current network using shortest paths.

    Parameters
    ----------
    env:
        Environment used to build candidate actions.
    alpha:
        Learning rate.
    gamma:
        Discount factor.
    epsilon:
        Initial exploration probability.
    epsilon_decay:
        Multiplicative decay applied after each observed transition.
    epsilon_min:
        Lower bound for epsilon.
    state_bins:
        Number of intervals used for normalized resource values.
    max_actions:
        Maximum number of candidate actions considered per decision.
    max_states:
        Maximum number of states retained in the sparse Q-table.
    seed:
        Random seed for reproducible exploration and action sampling.
    """

    def __init__(
        self,
        env: Any,
        *,
        alpha: float = 0.1,
        gamma: float = 0.95,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.05,
        state_bins: int = 10,
        max_actions: int = 128,
        max_states: int = 50_000,
        seed: int | None = None,
    ) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        if not 0.0 <= gamma <= 1.0:
            raise ValueError("gamma must be in [0, 1]")
        if not 0.0 <= epsilon <= 1.0:
            raise ValueError("epsilon must be in [0, 1]")
        if not 0.0 < epsilon_decay <= 1.0:
            raise ValueError("epsilon_decay must be in (0, 1]")
        if not 0.0 <= epsilon_min <= 1.0:
            raise ValueError("epsilon_min must be in [0, 1]")
        if epsilon_min > epsilon:
            raise ValueError("epsilon_min cannot exceed epsilon")
        if state_bins < 2 or max_actions < 1 or max_states < 1:
            raise ValueError("state_bins, max_actions and max_states must be positive")

        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.epsilon_decay = float(epsilon_decay)
        self.epsilon_min = float(epsilon_min)
        self.state_bins = int(state_bins)
        self.max_actions = int(max_actions)
        self.max_states = int(max_states)
        self.rng = random.Random(seed)

        self.action_space = ActionSpace(env.network, manager=env.manager)
        self.state_encoder = StateEncoder(env.network)
        self.min_finish = MinFinishPolicy(self.action_space)

        # OrderedDict gives a simple LRU-style bound without allocating a
        # dense table.  Values are {action_server_tuple: q_value}.
        self.q_table: OrderedDict[StateKey, dict[ActionKey, float]] = OrderedDict()
        self._known_actions: dict[StateKey, tuple[Action, ...]] = {}
        self.training = True

    def state_key(self, state: dict[str, Any]) -> StateKey:
        """Convert a raw environment observation into a compact hashable key."""
        normalized = self.state_encoder.normalize(state)
        values: list[Hashable] = [int(float(normalized.get("time", 0.0)))]

        for node in self.state_encoder.layout.nodes:
            resources = normalized["node_resources"].get(node, {})
            values.extend(self._bucket(resources.get(name, 0.0)) for name in ("cpu", "ram", "hdd"))

        for edge in self.state_encoder.layout.edges:
            values.append(self._bucket(normalized["link_bandwidth"].get(edge, 0.0)))

        request = normalized.get("current_request")
        if request is None:
            values.append(None)
        else:
            values.append(
                (
                    tuple(request.get("vnf_chain", [])),
                    request.get("source"),
                    request.get("destination"),
                    self._number_bucket(request.get("bandwidth", 0.0)),
                    self._number_bucket(request.get("deadline", 0.0)),
                )
            )
        return tuple(values)

    def select_action(self, state: dict[str, Any], env: Any) -> Action | None:
        """Choose epsilon-greedily among bounded feasible placement actions."""
        state_key = self.state_key(state)
        actions = self._candidate_actions(env)
        if not actions:
            return None

        self._known_actions[state_key] = tuple(actions)
        values = self.q_table.setdefault(state_key, {})
        self._touch_state(state_key)
        for action in actions:
            values.setdefault(self.action_key(action), 0.0)

        if self.training and self.rng.random() < self.epsilon:
            return self.rng.choice(actions)

        best_value = max(values[self.action_key(action)] for action in actions)
        best = [action for action in actions if values[self.action_key(action)] == best_value]
        return self.rng.choice(best)

    def observe(
        self,
        state: dict[str, Any],
        action: Action | None,
        reward: float,
        next_state: dict[str, Any],
        terminated: bool,
    ) -> None:
        """Apply the one-step Q-learning update immediately."""
        if action is None:
            return

        current_key = self.state_key(state)
        action_key = self.action_key(action)
        current_values = self.q_table.setdefault(current_key, {})
        old_value = current_values.get(action_key, 0.0)

        next_key = self.state_key(next_state)
        next_values = self.q_table.get(next_key, {})
        max_next = max(next_values.values(), default=0.0)
        target = float(reward) if terminated else float(reward) + self.gamma * max_next
        current_values[action_key] = old_value + self.alpha * (target - old_value)
        self._touch_state(current_key)
        self._trim_table()

        if self.training:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def train(self) -> None:
        self.training = True

    def eval(self) -> None:
        self.training = False

    @staticmethod
    def action_key(action: Action) -> ActionKey:
        """Use placement only as the Q-table action identity."""
        return tuple(action.servers)

    def _candidate_actions(self, env: Any) -> list[Action]:
        request = env.current_request
        if request is None:
            return []

        duration = env._duration(request)
        candidates = self.action_space.candidate_servers(
            request,
            env.vnfs,
            manager=env.manager,
            t1=0,
            t2=duration,
        )
        if any(not options for options in candidates):
            return []

        combinations = 1
        for options in candidates:
            combinations *= len(options)

        server_tuples: list[tuple[Any, ...]]
        if combinations <= self.max_actions:
            server_tuples = list(itertools.product(*candidates))
        else:
            server_tuples = []
            seen: set[tuple[Any, ...]] = set()
            while len(server_tuples) < self.max_actions:
                servers = tuple(self.rng.choice(options) for options in candidates)
                if servers not in seen:
                    seen.add(servers)
                    server_tuples.append(servers)

        actions: list[Action] = []
        for servers in server_tuples:
            try:
                route = self.action_space.route(request, servers)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            actions.append(Action(servers, route, request.idx))

        # Keep the domain heuristic available as a sensible action, even when
        # epsilon has already become small.
        min_finish = self.min_finish.choose(env)
        if min_finish is not None and self.action_key(min_finish) not in {
            self.action_key(action) for action in actions
        }:
            actions.append(min_finish)
        return actions[: self.max_actions]

    def _bucket(self, value: Any) -> int:
        try:
            clipped = max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            clipped = 0.0
        return min(self.state_bins, int(clipped * self.state_bins))

    @staticmethod
    def _number_bucket(value: Any) -> int | float:
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return 0.0

    def _touch_state(self, state_key: StateKey) -> None:
        self.q_table.move_to_end(state_key)

    def _trim_table(self) -> None:
        while len(self.q_table) > self.max_states:
            oldest, _ = self.q_table.popitem(last=False)
            self._known_actions.pop(oldest, None)


__all__ = ["QLearningAgent"]
