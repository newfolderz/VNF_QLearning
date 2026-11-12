"""Dataset loader for the JSON files in ``data/generated``.

The loader is deliberately kept outside ``training``.  It converts the JSON
schema into the domain objects consumed by :class:`NetworkEnv`:

    dataset JSON -> Network, list[VNF], list[Request] -> NetworkEnv
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from typing import Any, Iterator, Mapping

import networkx as nx

from ..domain.network import Network
from ..domain.request import Request
from ..domain.vnf import VNF
from ..environment.network_env import NetworkEnv


@dataclass(frozen=True, slots=True)
class LoadedDataset:
    """Parsed dataset and its metadata.

    The object can also be unpacked as ``network, vnfs, requests`` to keep the
    simple tuple-style API convenient.
    """

    network: Network
    vnfs: list[VNF]
    requests: list[Request]
    metadata: dict[str, Any]

    def __iter__(self) -> Iterator[Any]:
        yield self.network
        yield self.vnfs
        yield self.requests


def load_dataset(path: str | Path, *, max_horizon: int | None = None) -> LoadedDataset:
    """Load one generated dataset JSON file.

    Parameters
    ----------
    path:
        Path to a file such as ``data/generated/dataset_nsf_uniform_easy_v1.json``.
    max_horizon:
        Resource reservation horizon.  Defaults to dataset duration, or 30 if
        the metadata does not specify a duration.
    """
    dataset_path = Path(path)
    with dataset_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, Mapping):
        raise ValueError("dataset root must be a JSON object")
    metadata = dict(_mapping(payload, "metadata"))
    duration = _positive_int(metadata, "duration", default=30)
    train_slots = _positive_or_zero_int(metadata, "train_slots", default=duration)
    test_slots = _positive_or_zero_int(
        metadata, "test_slots", default=duration - train_slots
    )
    if train_slots + test_slots != duration:
        raise ValueError(
            "metadata duration must equal train_slots + test_slots"
        )
    network_data = _mapping(payload, "network")
    node_data = _list(network_data, "nodes")
    link_data = _list(network_data, "links")

    horizon = duration if max_horizon is None else int(max_horizon)
    if horizon < 1:
        raise ValueError("max_horizon must be positive")

    network = Network(max_horizon=horizon)
    server_ids: list[Any] = []
    node_ids: set[Any] = set()
    for node in node_data:
        node_id = node.get("id")
        if node_id is None:
            raise ValueError("every network node requires an id")
        if node_id in node_ids:
            raise ValueError(f"duplicate network node id: {node_id!r}")
        node_ids.add(node_id)
        node_type = node.get("type", "switch")
        if node_type == "server":
            network.add_server_node(
                node_id,
                _number(node, "cpu_capacity"),
                _number(node, "ram_capacity"),
                _number(node, "hdd_capacity"),
                _number(node, "cpu_cost"),
                _number(node, "ram_cost"),
                _number(node, "hdd_cost"),
                _number(node, "delay"),
            )
            server_ids.append(node_id)
        elif node_type == "switch":
            network.add_switch_node(node_id)
        else:
            raise ValueError(f"unsupported network node type: {node_type!r}")

    for link in link_data:
        source = link.get("source")
        target = link.get("target")
        if source not in node_ids or target not in node_ids:
            raise ValueError(
                f"link endpoints must reference known nodes: {source!r}, {target!r}"
            )
        if source == target:
            raise ValueError(f"self-loop is not supported: {source!r}")
        network.add_link(
            source,
            target,
            _number(link, "bandwidth_capacity"),
            _number(link, "delay"),
        )

    declared_servers = network_data.get("server_nodes")
    if declared_servers is not None:
        if not isinstance(declared_servers, list):
            raise ValueError("network.server_nodes must be a list")
        if set(declared_servers) != set(server_ids):
            raise ValueError(
                "network.server_nodes does not match nodes with type='server'"
            )
    if network.G.number_of_nodes() > 0 and not nx.is_connected(network.G):
        raise ValueError("network topology must be connected")

    vnf_data = _list(payload, "vnfs")
    vnf_ids = [item.get("id") for item in vnf_data]
    if vnf_ids != list(range(len(vnf_data))):
        raise ValueError("VNF ids must be contiguous and ordered from zero")
    vnfs = [_load_vnf(item, server_ids) for item in vnf_data]
    request_data = _list(payload, "requests")
    requests = [_load_request(item) for item in request_data]
    _validate_requests(requests, node_ids, len(vnfs))
    requests.sort(key=lambda request: (request.arrival, request.idx))
    return LoadedDataset(network, vnfs, requests, metadata)


def load_environment(
    path: str | Path,
    *,
    split: str = "all",
    max_horizon: int | None = None,
    rho: float = 1.0,
    max_steps: int | None = None,
    train_slots: int | None = None,
    rebase_time: bool = False,
) -> NetworkEnv:
    """Load a dataset and construct a ``NetworkEnv``.

    ``split="train"`` uses requests arriving before ``train_slots``;
    ``split="test"`` uses the remaining requests.  ``split="all"`` keeps all
    requests.  The environment's step limit defaults to the corresponding
    metadata duration unless explicitly supplied.
    """
    if split not in {"all", "train", "test"}:
        raise ValueError("split must be 'all', 'train' or 'test'")

    dataset = load_dataset(path, max_horizon=max_horizon)
    requests = dataset.requests
    duration = _positive_int(
        dataset.metadata, "duration", default=dataset.network.max_horizon
    )
    boundary = (
        _positive_or_zero_int(dataset.metadata, "train_slots", default=duration)
        if train_slots is None
        else int(train_slots)
    )
    if not 0 < boundary < duration:
        raise ValueError("train_slots must be between 1 and duration - 1")

    if split == "train":
        requests = [request for request in requests if float(request.arrival) < boundary]
        # A step handles one pending request.  With bursty arrivals, the
        # queue may need extra steps after the arrival window closes.
        default_steps = (
            _required_steps(requests, boundary) if max_steps is None else max_steps
        )
    elif split == "test":
        requests = [request for request in requests if float(request.arrival) >= boundary]
        if rebase_time:
            requests = [_shift_request(request, boundary) for request in requests]
            default_steps = (
                _required_steps(requests, duration - boundary)
                if max_steps is None
                else max_steps
            )
        else:
            default_steps = (
                _required_steps(requests, duration)
                if max_steps is None
                else max_steps
            )
    else:
        default_steps = duration

    return NetworkEnv(
        dataset.network,
        dataset.vnfs,
        requests,
        rho=rho,
        max_steps=max_steps if max_steps is not None else default_steps,
    )


def _load_vnf(data: Mapping[str, Any], server_ids: list[Any]) -> VNF:
    """Convert scalar or per-server JSON processing delay to ``VNF.df``."""
    processing_delay = data.get("processing_delay", data.get("delay"))
    if isinstance(processing_delay, Mapping):
        delays = {
            _coerce_node_id(node): float(value)
            for node, value in processing_delay.items()
        }
    else:
        if processing_delay is None:
            raise ValueError("every VNF requires processing_delay")
        delays = {node: float(processing_delay) for node in server_ids}

    return VNF(
        _number(data, "cpu_demand"),
        _number(data, "ram_demand"),
        _number(data, "hdd_demand"),
        delays,
    )


def _load_request(data: Mapping[str, Any]) -> Request:
    """Convert a generated request while preserving absolute deadlines."""
    start_time = data.get("start_time", data.get("start_at"))
    if start_time is None:
        start_time = data.get("arrival_time", data.get("arrival", 0))
    start_time = _number({"start_time": start_time}, "start_time")
    return Request(
        data["id"],
        data.get("arrival_time", data.get("arrival", 0)),
        data.get("source", data.get("start")),
        data.get("destination", data.get("dest")),
        list(data.get("vnf_chain", data.get("Fr", []))),
        _number(data, "bandwidth", default=data.get("br", 0.0)),
        _number(data, "deadline", default=data.get("dr", 1.0)),
        start_time=start_time,
    )


def _validate_requests(
    requests: list[Request], node_ids: set[Any], vnf_count: int
) -> None:
    request_ids: set[Any] = set()
    for request in requests:
        if request.idx in request_ids:
            raise ValueError(f"duplicate request id: {request.idx!r}")
        request_ids.add(request.idx)
        if request.st not in node_ids or request.d not in node_ids:
            raise ValueError(
                f"request {request.idx!r} references an unknown endpoint"
            )
        if not request.Fr:
            raise ValueError(f"request {request.idx!r} has an empty VNF chain")
        if any(not isinstance(vnf_id, int) or not 0 <= vnf_id < vnf_count for vnf_id in request.Fr):
            raise ValueError(f"request {request.idx!r} references an unknown VNF")
        for name, value in (
            ("arrival_time", request.arrival),
            ("start_time", request.start_time),
            ("bandwidth", request.br),
            ("deadline", request.dr),
        ):
            if not isfinite(float(value)):
                raise ValueError(f"request {request.idx!r} has non-finite {name}")
        if request.start_time < request.arrival:
            raise ValueError(f"request {request.idx!r} starts before arrival")
        if request.dr <= request.arrival:
            raise ValueError(f"request {request.idx!r} deadline must be after arrival")
        if request.br < 0:
            raise ValueError(f"request {request.idx!r} has negative bandwidth")


def _shift_request(request: Request, offset: int) -> Request:
    """Return a request on a zero-based timeline for an isolated split."""
    return Request(
        request.idx,
        float(request.arrival) - offset,
        request.st,
        request.d,
        list(request.Fr),
        request.br,
        float(request.dr) - offset,
        start_time=float(request.start_time) - offset,
    )


def _required_steps(requests: list[Request], minimum_steps: int) -> int:
    """Return enough one-request-per-step ticks to drain all arrivals."""
    arrivals = sorted(float(request.arrival) for request in requests)
    pending = 0
    next_arrival = 0
    time = 0
    while next_arrival < len(arrivals) or pending:
        while next_arrival < len(arrivals) and arrivals[next_arrival] <= time:
            pending += 1
            next_arrival += 1
        if pending:
            pending -= 1
        time += 1
    return max(int(minimum_steps), time)


def _mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"dataset field {key!r} must be an object")
    return value


def _list(parent: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = parent.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"dataset field {key!r} must be a list")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"dataset field {key!r} must contain objects")
    return value


def _number(data: Mapping[str, Any], key: str, *, default: Any = None) -> float:
    value = data.get(key, default)
    if value is None:
        raise ValueError(f"missing numeric field {key!r}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"field {key!r} must be numeric") from exc


def _positive_int(data: Mapping[str, Any], key: str, *, default: int) -> int:
    value = data.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"field {key!r} must be an integer") from exc
    if parsed < 1:
        raise ValueError(f"field {key!r} must be positive")
    return parsed


def _positive_or_zero_int(data: Mapping[str, Any], key: str, *, default: int) -> int:
    value = data.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"field {key!r} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"field {key!r} must not be negative")
    return parsed


def _coerce_node_id(value: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


__all__ = ["LoadedDataset", "load_dataset", "load_environment"]
