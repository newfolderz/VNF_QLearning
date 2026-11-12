from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import networkx as nx


TOPOLOGIES = ("nsf", "conus", "cogent")
SERVER_DISTRIBUTIONS = ("uniform", "rural", "urban", "centers")
DIFFICULTIES = ("easy", "normal", "hard")
VERSIONS = (1, 2, 3)
VNF_COUNT = 10
DURATION = 50
REQUEST_COUNT = 50
TRAIN_SLOTS = 10


# def reallocate_VNF_resource(manager: Manager, timeline: list, resource: str,
#                             VNF_range: list):
#     solver = pywraplp.Solver.CreateSolver('SCIP')
#     if not solver:
#         return
#
#     infinity = solver.infinity()
#     min_VNF = solver.NumVar(0, infinity, 'cap')
#
#     y = []
#     for i, vnf in enumerate(manager.F):
#         y.append(solver.NumVar(0, infinity, f'y_{i}'))
#         solver.Add(y[i] - min_VNF >= 0)
#         solver.Add(y[i] >= VNF_range[0])
#         solver.Add(y[i] <= VNF_range[1])
#
#     for sfc_list in timeline:
#         constraints = {}
#         for node in manager.network.server_nodes:
#             constraints[node] = solver.Constraint(0, manager.network.G
#                                                   .nodes[node][f'{resource}_cap'])
#         for sfc in sfc_list:
#             for vnf_id, node in zip(sfc.request.Fr, sfc.F_nodes):
#                 constraints[node].SetCoefficient(y[vnf_id], constraints[node]
#                                                  .GetCoefficient(y[vnf_id]) + 1)
#
#     solver.Maximize(min_VNF)
#     status = solver.Solve()
#     assert status == solver.OPTIMAL, 'Impossible reallocation model!'
#
#     for i, vnf in enumerate(manager.F):
#         setattr(vnf, f'{resource}f', random.uniform(0.9, 1) * y[i].solution_value())
#
#
# def reallocate_node_and_VNF_resource(manager: Manager, timeline: list, resource: str,
#                                      VNF_range: list, node_range: list):
#     solver = pywraplp.Solver.CreateSolver('SCIP')
#     if not solver:
#         return
#
#     infinity = solver.infinity()
#     min_VNF = solver.NumVar(0, infinity, 'VNF_cap')
#     max_node = solver.NumVar(0, infinity, 'node_cap')
#
#     y = []
#     z = dict()
#     for i, vnf in enumerate(manager.F):
#         y.append(solver.NumVar(0, infinity, f'y_{i}'))
#         solver.Add(y[i] >= VNF_range[0])
#         solver.Add(y[i] <= VNF_range[1])
#         solver.Add(y[i] - min_VNF >= 0)
#
#     for node in manager.network.server_nodes:
#         z[node] = solver.NumVar(0, infinity, f'z_{node}')
#         solver.Add(z[node] >= node_range[0])
#         solver.Add(z[node] <= node_range[1])
#         solver.Add(z[node] - max_node <= 0)
#
#     for sfc_list in timeline:
#         constraints = {}
#         for node in manager.network.server_nodes:
#             ct = solver.Constraint(-infinity, 0)
#             ct.SetCoefficient(z[node], -1)
#             constraints[node] = ct
#         for sfc in sfc_list:
#             for vnf_id, node in zip(sfc.request.Fr, sfc.F_nodes):
#                 constraints[node].SetCoefficient(y[vnf_id], constraints[node]
#                                                  .GetCoefficient(y[vnf_id]) + 1)
#
#     solver.Maximize(min_VNF / VNF_range[1] - max_node / node_range[1])
#     status = solver.Solve()
#     assert status == solver.OPTIMAL, 'Impossible reallocation model!'
#
#     for i, vnf in enumerate(manager.F):
#         setattr(vnf, f'{resource}f', random.uniform(0.9, 1) * y[i].solution_value())
#     for node in manager.network.server_nodes:
#         manager.network.G.nodes[node][f'{resource}_cap'] \
#             = random.uniform(1, 1.1) * z[node].solution_value()
#
#
# def reallocate_bandwidth(manager: Manager, timeline: list, requests: list, bandwidth_range: list):
#     solver = pywraplp.Solver.CreateSolver('SCIP')
#     if not solver:
#         return
#
#     infinity = solver.infinity()
#     min_req = solver.NumVar(0, infinity, 'bandwidth_cap')
#
#     r = {}
#     for req in requests:
#         r[id(req)] = solver.NumVar(0, infinity, f'r_{id(req)}')
#         solver.Add(r[id(req)] >= bandwidth_range[0])
#         solver.Add(r[id(req)] <= bandwidth_range[1])
#         solver.Add(r[id(req)] - min_req >= 0)
#
#     for sfc_list in timeline:
#         constraints = {}
#         for u, v in manager.network.G.edges:
#             constraints[frozenset([u, v])] = solver.Constraint(0, manager.network.G[u][v]['b_cap'])
#         for sfc in sfc_list:
#             for u, v in zip(sfc.route_nodes[:-1], sfc.route_nodes[1:]):
#                 ct = constraints[frozenset([u, v])]
#                 ct.SetCoefficient(r[id(sfc.request)], ct.GetCoefficient(r[id(sfc.request)] + 1))
#
#     solver.Maximize(min_req)
#     status = solver.Solve()
#     assert status == solver.OPTIMAL, 'Impossible reallocation model!'
#
#     for req in requests:
#         req.br = random.uniform(0.9, 1) * r[id(req)].solution_value()


def generate_test(graph: nx.Graph, scheme: str, server_distribution: str, duration: int, segments: int):
    # network parameters
    cpu_v = ram_v = hdd_v = [20, 50]
    bandwidth_l = [30, 120]
    cpu_cost = [100, 200]
    ram_cost = [50, 100]
    hdd_cost = [10, 30]
    delay_v = [0.1, 0.5]

    network = generate_network(graph, server_distribution,
                               cpu_v, ram_v, hdd_v, bandwidth_l,
                               cpu_cost, ram_cost, hdd_cost, delay_v)

    if type(segments) == int:
        avg_segments = sum(range(1, segments + 1)) / segments
    else:
        avg_segments = sum([p * (seg + 1)] for seg, p in enumerate(segments))
    if scheme in ['easy', 'normal']:
        # VNF parameters
        vnf_types = 10
        # cpu_f = ram_f = hdd_f = [2 / duration, 5 / duration]
        delay_f = [0.003 * duration, 0.01 * duration]

        # request parameters
        arrival_rate = 50
        # segments = (0.5, 0.3, 0.2)
        bandwidth_r = (0, 10)
        delay_ratio = (1, 1.2)

        # custom
        servers = len(network.server_nodes)
        limit = min(1.0, servers / arrival_rate / avg_segments)
        if scheme == 'normal':
            limit = min(1.0, 2.0 * servers / arrival_rate / avg_segments)
        cpu_f = ram_f = hdd_f = [1 * limit, 5 * limit]

    elif scheme == 'hard':
        # VNF parameters
        vnf_types = 10
        delay_f = [0.05 * duration, 0.1 * duration]

        # request parameters
        arrival_rate = 50
        # segments = (0.4, 0.3, 0.2, 0.1)
        bandwidth_r = (1, 20)
        delay_ratio = (1, 1.2)

        # custom
        servers = len(network.server_nodes)
        limit = min(1.0, servers / arrival_rate / avg_segments)
        cpu_f = ram_f = hdd_f = [10 * limit, 20 * limit]
    else:
        raise Exception('Scheme not found!')

    # generate
    VNFs = generate_vnf(network, scheme, server_distribution, vnf_types,
                        cpu_f, ram_f, hdd_f, delay_f)
    manager = Manager(network, VNFs)
    # results = generate_requests(scheme, manager, duration, arrival_rate,
    #                             segments, bandwidth_r, delay_ratio, True)
    # if results is None:
    #     return None, None
    # requests, timeline = results

    # # reallocate
    # for resource in ['c', 'r', 'h']:
    #     if resource == 'c':
    #         VNF_range = cpu_f
    #         node_range = cpu_v
    #     elif resource == 'r':
    #         VNF_range = ram_f
    #         node_range = ram_v
    #     elif resource == 'h':
    #         VNF_range = hdd_f
    #         node_range = hdd_v
    #     else:
    #         exit(-1)
    #
    #     if scheme == 'easy':
    #         reallocate_VNF_resource(manager, timeline, resource, VNF_range)
    #     elif scheme == 'normal':
    #         reallocate_node_and_VNF_resource(manager, timeline, resource, VNF_range, node_range)
    #
    # if scheme != 'hard':
    #     reallocate_bandwidth(manager, timeline, requests, (0, 100))
    requests = generate_requests(scheme, manager, duration, arrival_rate,
                                 segments, bandwidth_r, delay_ratio)
    if requests is None:
        return None, None
    return manager, requests


def read_topology(nodes_path: Path, edges_path: Path) -> nx.Graph:
    graph = nx.Graph()
    with nodes_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    for node_id, row in enumerate(rows[2:]):
        if len(row) >= 2:
            graph.add_node(node_id, x=float(row[0]), y=float(row[1]))
    with edges_path.open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.split()
            if len(fields) >= 2:
                u, v = int(fields[0]), int(fields[1])
                x1, y1 = graph.nodes[u]["x"], graph.nodes[u]["y"]
                x2, y2 = graph.nodes[v]["x"], graph.nodes[v]["y"]
                graph.add_edge(u, v, distance=((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5)
    return graph


def choose_servers(graph: nx.Graph, distribution: str, rng: random.Random) -> list[int]:
    nodes = sorted(graph.nodes)
    degree_order = sorted(nodes, key=lambda node: (-graph.degree[node], node))
    count = max(1, round(0.3 * len(nodes)))
    if distribution == "uniform":
        return sorted(rng.sample(nodes, count))
    if distribution == "urban":
        return sorted(degree_order[:count])
    if distribution == "rural":
        return sorted(degree_order[-count:])
    if distribution == "centers":
        return sorted(degree_order[:max(1, round(0.1 * len(nodes)))])
    raise ValueError(f"Unknown server distribution: {distribution}")


def build_dataset(graph: nx.Graph, topology: str, distribution: str,
                  difficulty: str, version: int, rng: random.Random,
                  *, duration: int = DURATION,
                  train_slots: int = TRAIN_SLOTS) -> dict[str, Any]:
    if duration < 2:
        raise ValueError("duration must be at least 2 slots")
    if not 0 < train_slots < duration:
        raise ValueError("train_slots must be between 1 and duration - 1")
    server_nodes = set(choose_servers(graph, distribution, rng))
    demand_ranges = {"easy": (1.0, 3.0), "normal": (2.0, 6.0), "hard": (5.0, 12.0)}
    bandwidth_ranges = {"easy": (0.0, 10.0), "normal": (1.0, 15.0), "hard": (1.0, 20.0)}
    demand_range, bandwidth_range = demand_ranges[difficulty], bandwidth_ranges[difficulty]
    max_distance = max((d["distance"] for _, _, d in graph.edges(data=True)), default=1.0)

    nodes = []
    for node in sorted(graph.nodes):
        if node in server_nodes:
            nodes.append({"id": node, "type": "server",
                          "cpu_capacity": round(rng.uniform(20, 50), 4),
                          "ram_capacity": round(rng.uniform(20, 50), 4),
                          "hdd_capacity": round(rng.uniform(20, 50), 4),
                          "cpu_cost": round(rng.uniform(100, 200), 4),
                          "ram_cost": round(rng.uniform(50, 100), 4),
                          "hdd_cost": round(rng.uniform(10, 30), 4),
                          "delay": round(rng.uniform(0.1, 0.5), 4)})
        else:
            nodes.append({"id": node, "type": "switch"})

    links = []
    for u, v, data in graph.edges(data=True):
        links.append({"source": u, "target": v, "distance": round(data["distance"], 6),
                      "bandwidth_capacity": round(rng.uniform(30, 120), 4),
                      "delay": round(0.3 * data["distance"] / max_distance, 6)})

    vnfs = [{"id": i, "cpu_demand": round(rng.uniform(*demand_range), 4),
             "ram_demand": round(rng.uniform(*demand_range), 4),
             "hdd_demand": round(rng.uniform(*demand_range), 4),
             "processing_delay": round(rng.uniform(0.003, 0.01), 6)}
            for i in range(10)]

    switches = sorted(set(graph.nodes) - server_nodes)
    max_segments = {"easy": 2, "normal": 3, "hard": 4}[difficulty]
    # Keep the total workload fixed while allowing a realistic temporal
    # workload: a slot may contain no request, one request, or several
    # requests.  Sampling with replacement intentionally permits collisions.
    arrival_times = sorted(rng.choices(range(duration), k=REQUEST_COUNT))
    requests = []
    for request_id, arrival_time in enumerate(arrival_times):
        source, target = rng.sample(switches, 2)
        route = nx.shortest_path(graph, source, target, weight="distance")
        chain = rng.sample(range(10), rng.randint(1, max_segments))
        requests.append({"id": request_id, "arrival_time": arrival_time,
                         "start_time": arrival_time + rng.randint(0, 2),
                         "source": source, "destination": target,
                         "bandwidth": round(rng.uniform(*bandwidth_range), 4),
                         "deadline": round(arrival_time + len(route) + len(chain) * rng.uniform(1.0, 1.2), 4),
                         "vnf_chain": chain,
                         "placement_hint": [rng.choice(sorted(server_nodes)) for _ in chain],
                         "route_hint": route})

    return {"schema_version": "1.0",
            "metadata": {"topology": topology, "server_distribution": distribution,
                         "difficulty": difficulty, "version": version, "duration": duration,
                         "train_slots": train_slots, "test_slots": duration - train_slots},
            "network": {"nodes": nodes, "links": links, "server_nodes": sorted(server_nodes)},
            "vnfs": vnfs, "requests": requests}


def generate_all(output_dir: Path, data_dir: Path, seed: int = 2026, force: bool = False) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for topology in TOPOLOGIES:
        graph = read_topology(data_dir / "topologies" / f"{topology}_nodes.csv",
                              data_dir / "topologies" / f"{topology}_edges.txt")
        for distribution in SERVER_DISTRIBUTIONS:
            for difficulty in DIFFICULTIES:
                for version in VERSIONS:
                    filename = f"dataset_{topology}_{distribution}_{difficulty}_v{version}.json"
                    path = output_dir / filename
                    if path.exists() and not force:
                        dataset = json.loads(path.read_text(encoding="utf-8"))
                    else:
                        key = f"{seed}:{topology}:{distribution}:{difficulty}:{version}"
                        case_seed = int(hashlib.sha256(key.encode()).hexdigest()[:16], 16)
                        dataset = build_dataset(graph, topology, distribution, difficulty,
                                                version, random.Random(case_seed))
                        path.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
                    manifest.append({"file": filename, **dataset["metadata"]})
    catalog = [{"id": i, "name": f"vnf_{i}", "description": "Generated VNF type"} for i in range(10)]
    (output_dir / "vnf_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return len(manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the 108 experiment datasets")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    count = generate_all(root / "data" / "generated", root / "data", args.seed, args.force)
    print(f"Generated/verified {count} datasets in {root / 'data' / 'generated'}")
