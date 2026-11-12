"""Training and evaluation loops for the project agents.

The trainer follows the environment contract used by ``NetworkEnv``::

    state = env.reset(...)
    next_state, reward, terminated, truncated, info = env.step(action)

It deliberately does not know about DQN, replay memory or neural networks.
The same loop can therefore be used by ``QLearningAgent`` and future agents.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from ..agents.base import BaseAgent


RequestsFactory = Callable[[int], Iterable[Any]]


class Trainer:
    """Run episodes for an agent and return serializable episode metrics.

    Parameters
    ----------
    agent:
        Agent implementing ``select_action`` and optionally ``observe``.
    env:
        Environment implementing the ``NetworkEnv`` reset/step contract.
    """

    def __init__(self, agent: BaseAgent, env: Any) -> None:
        if not hasattr(agent, "select_action") or not hasattr(agent, "observe"):
            raise TypeError("agent must implement select_action() and observe()")
        if not hasattr(env, "reset") or not hasattr(env, "step"):
            raise TypeError("env must implement reset() and step()")
        self.agent = agent
        self.env = env

    def train(
        self,
        episodes: int = 1,
        *,
        requests: Iterable[Any] | None = None,
        request_factory: RequestsFactory | None = None,
        seed: int | None = None,
        max_steps_per_episode: int | None = None,
    ) -> list[dict[str, Any]]:
        """Train for ``episodes`` and return one metrics dict per episode.

        ``requests`` is reused on every episode.  Use ``request_factory`` when
        each episode must receive a different dataset or request split.  The
        factory receives the zero-based episode index.
        """
        self._validate_episode_arguments(episodes, requests, request_factory)
        self.agent.train()
        history: list[dict[str, Any]] = []

        for episode in range(episodes):
            episode_requests = (
                request_factory(episode) if request_factory is not None else requests
            )
            history.append(
                self.run_episode(
                    episode=episode,
                    requests=episode_requests,
                    seed=None if seed is None else seed + episode,
                    training=True,
                    max_steps_per_episode=max_steps_per_episode,
                )
            )
        return history

    def evaluate(
        self,
        episodes: int = 1,
        *,
        requests: Iterable[Any] | None = None,
        request_factory: RequestsFactory | None = None,
        seed: int | None = None,
        max_steps_per_episode: int | None = None,
    ) -> list[dict[str, Any]]:
        """Evaluate without updating the agent or decaying epsilon."""
        self._validate_episode_arguments(episodes, requests, request_factory)
        self.agent.eval()
        history: list[dict[str, Any]] = []

        for episode in range(episodes):
            episode_requests = (
                request_factory(episode) if request_factory is not None else requests
            )
            history.append(
                self.run_episode(
                    episode=episode,
                    requests=episode_requests,
                    seed=None if seed is None else seed + episode,
                    training=False,
                    max_steps_per_episode=max_steps_per_episode,
                )
            )
        return history

    def run_episode(
        self,
        *,
        episode: int = 0,
        requests: Iterable[Any] | None = None,
        seed: int | None = None,
        training: bool = True,
        max_steps_per_episode: int | None = None,
    ) -> dict[str, Any]:
        """Run one episode using the project's five-value step output."""
        if training:
            self.agent.train()
        else:
            self.agent.eval()

        reset_kwargs: dict[str, Any] = {}
        if requests is not None:
            reset_kwargs["requests"] = requests
        if seed is not None:
            reset_kwargs["seed"] = seed

        state = self.env.reset(**reset_kwargs)
        terminated = False
        truncated = False
        steps = 0
        total_reward = 0.0
        accepted_steps = 0
        rejected_steps = 0
        last_info: dict[str, Any] = {}

        while not terminated and not truncated:
            if (
                max_steps_per_episode is not None
                and steps >= max_steps_per_episode
            ):
                truncated = True
                break

            action = self.agent.select_action(state, self.env)
            next_state, reward, terminated, truncated, info = self.env.step(action)

            if training:
                self.agent.observe(
                    state,
                    action,
                    float(reward),
                    next_state,
                    bool(terminated or truncated),
                )

            total_reward += float(reward)
            accepted_steps += int(bool(info.get("accepted", False)))
            rejected_steps += int(
                info.get("request_id") is not None
                and not bool(info.get("accepted", False))
            )
            steps += 1
            last_info = dict(info)
            state = next_state

        metrics = self._episode_metrics(
            episode=episode,
            steps=steps,
            total_reward=total_reward,
            accepted_steps=accepted_steps,
            rejected_steps=rejected_steps,
            terminated=terminated,
            truncated=truncated,
            last_info=last_info,
        )
        return metrics

    def _episode_metrics(
        self,
        *,
        episode: int,
        steps: int,
        total_reward: float,
        accepted_steps: int,
        rejected_steps: int,
        terminated: bool,
        truncated: bool,
        last_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine environment tracker metrics with trainer-level metrics."""
        tracker = getattr(self.env, "reward_tracker", None)
        summary = tracker.summary() if tracker is not None else {}

        requests = int(summary.get("requests", accepted_steps + rejected_steps))
        accepted = int(summary.get("accepted", accepted_steps))
        acceptance_rate = float(
            summary.get("acceptance_rate", accepted / requests if requests else 0.0)
        )

        metrics: dict[str, Any] = {
            "episode": episode,
            "steps": steps,
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "total_reward": total_reward,
            "requests": requests,
            "accepted": accepted,
            "rejected": requests - accepted,
            "acceptance_rate": acceptance_rate,
            "total_cost": float(summary.get("total_cost", 0.0)),
            "tracker_total_reward": float(summary.get("total_reward", total_reward)),
            "last_info": last_info,
        }

        if hasattr(self.agent, "epsilon"):
            metrics["epsilon"] = float(self.agent.epsilon)
        if hasattr(self.agent, "q_table"):
            q_table = self.agent.q_table
            metrics["q_states"] = len(q_table)
            metrics["q_entries"] = sum(len(values) for values in q_table.values())
        return metrics

    @staticmethod
    def _validate_episode_arguments(
        episodes: int,
        requests: Iterable[Any] | None,
        request_factory: RequestsFactory | None,
    ) -> None:
        if not isinstance(episodes, int) or episodes < 1:
            raise ValueError("episodes must be a positive integer")
        if requests is not None and request_factory is not None:
            raise ValueError("provide either requests or request_factory, not both")


def train_agent(
    agent: BaseAgent,
    env: Any,
    episodes: int = 1,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Convenience wrapper around :class:`Trainer.train`."""
    return Trainer(agent, env).train(episodes, **kwargs)


__all__ = ["Trainer", "RequestsFactory", "train_agent"]
