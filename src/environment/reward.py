"""Reward calculation and episode-level acceptance statistics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RewardBreakdown:
    """Auditable components of one request reward."""

    reward: float
    accepted: bool
    acceptance_component: float
    cost_component: float


class RewardCalculator:
    """Compute reward as acceptance benefit minus normalized placement cost."""

    def __init__(self, rho: float = 1.0, *, cost_weight: float = 1.0,
                 cost_scale: float = 1.0, rejection_penalty: float | None = None) -> None:
        if cost_scale <= 0:
            raise ValueError("cost_scale must be positive")
        if cost_weight < 0:
            raise ValueError("cost_weight must be non-negative")
        self.rho = float(rho)
        self.cost_weight = float(cost_weight)
        self.cost_scale = float(cost_scale)
        self.rejection_penalty = -abs(float(rejection_penalty)) if rejection_penalty is not None else -self.rho

    def breakdown(self, accepted: bool, *, cost: float = 0.0) -> RewardBreakdown:
        """Return reward and its acceptance/cost components."""
        if cost < 0:
            raise ValueError("cost must be non-negative")
        if not accepted:
            return RewardBreakdown(self.rejection_penalty, False, self.rejection_penalty, 0.0)
        acceptance = self.rho
        cost_component = self.cost_weight * float(cost) / self.cost_scale
        return RewardBreakdown(acceptance - cost_component, True, acceptance, -cost_component)

    def compute(self, accepted: bool, *, cost: float = 0.0) -> float:
        """Return only the scalar reward."""
        return self.breakdown(accepted, cost=cost).reward


class RewardTracker:
    """Track request-level acceptance and cost over an episode."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.requests = 0
        self.accepted = 0
        self.total_cost = 0.0
        self.total_reward = 0.0

    def update(self, result: RewardBreakdown, *, cost: float = 0.0) -> None:
        self.requests += 1
        self.accepted += int(result.accepted)
        self.total_cost += float(cost) if result.accepted else 0.0
        self.total_reward += result.reward

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.requests if self.requests else 0.0

    def summary(self) -> dict[str, float | int]:
        return {
            "requests": self.requests,
            "accepted": self.accepted,
            "acceptance_rate": self.acceptance_rate,
            "total_cost": self.total_cost,
            "total_reward": self.total_reward,
        }


__all__ = ["RewardBreakdown", "RewardCalculator", "RewardTracker"]
