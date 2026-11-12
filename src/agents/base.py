"""Common interface for agents.

The empty hooks are intentional: they keep the training loop compatible with
future tabular Q-learning and DQN agents without introducing replay or a
neural network at this stage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Interface shared by heuristic and learning agents."""

    @abstractmethod
    def select_action(self, state: dict[str, Any], env: Any) -> Any:
        """Return an action accepted by ``env.step``."""
        raise NotImplementedError

    def observe(
        self,
        state: dict[str, Any],
        action: Any,
        reward: float,
        next_state: dict[str, Any],
        terminated: bool,
    ) -> None:
        """Receive one transition; learning agents can override this later."""
        del state, action, reward, next_state, terminated

    def train(self) -> None:
        """Switch to training mode when an agent needs one."""

    def eval(self) -> None:
        """Switch to evaluation mode when an agent needs one."""
