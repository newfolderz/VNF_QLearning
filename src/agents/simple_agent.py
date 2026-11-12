"""Simple non-learning agent implementations."""

from __future__ import annotations

from typing import Any

from ..environment.action import ActionSpace
from .base import BaseAgent
from .MinFinishPolicy import MinFinishPolicy


class MinFinishAgent(BaseAgent):
    """Agent using the earliest-VNF-finish placement policy."""

    def __init__(self, env: Any) -> None:
        self.action_space = ActionSpace(env.network, manager=env.manager)
        self.policy = MinFinishPolicy(self.action_space)

    def select_action(self, state: dict[str, Any], env: Any) -> Any:
        del state
        return self.policy.choose(env)


__all__ = ["MinFinishAgent"]