import random
from collections import defaultdict
from copy import deepcopy

import networkx as nx
import numpy as np
import scipy

from simulation.generator.graph_gen import file_to_graph
from simulation.generator.network_gen import generate_network, generate_vnf
from simulation.network_manager import Manager
from simulation.requests import Request, SFC
from simulation.io import test_export

def create_path(G: nx.Graph, source, target, num: int):
    idx = 0
    paths = []
    for path in nx.shortest_simple_paths(G, source, target):
        paths.append(path)
        idx += 1
        if idx == num:
            break
    return random.choice(paths)


def choose_close_node(target, candidates: list, distances):
    """choose the candidate that closest to target"""
    probs = np.array([distances[target][node] for node in candidates])
    probs = np.max(probs) - probs + 1
    probs = probs / np.sum(probs)
    return np.random.choice(candidates, p=probs)


def create_feasible_sfc(manager: Manager, arrival, start, segments,
                        bandwidth, delay_ratio, distances):
    # init number of VNF demands and start node
    if type(segments) == int:
        segments = np.random.choice(list(range(1, segments + 1)))
    else:
        segments = np.random.choice(list(range(1, len(segments) + 1)), p=segments)

    st = random.choice(manager.network.switch_nodes)

    full_path = [st]
    Fr = []
    vnf_servers = []

    # build segments between VNF servers
    current = st
    for _ in range(segments):
        candidate_nodes = []
        trials = 0
        candidate_VNFs = list(range(len(manager.F)))
        if len(Fr) > 0:
            candidate_VNFs.remove(Fr[-1])
        while len(candidate_nodes) == 0 and trials < 20:
            # select VNF
            vnf_id = random.choice(candidate_VNFs)
            vnf = manager.F[vnf_id]
            Fr.append(vnf_id)

            # select server node for VNF
            candidate_nodes = [node for node in manager.network.server_nodes
                               if manager.check_deploy_vnf(node, vnf)]
            trials += 1

        if len(candidate_nodes) == 0:
            return
        #print(f"Current node: {current}, Candidate nodes: {candidate_nodes}, VNF ID: {vnf_id}, VNF resources: CPU {vnf.cf}, RAM {vnf.rf}, HDD {vnf.hf}, Delay {vnf.df}")
        chosen_node = choose_close_node(current, candidate_nodes, distances)
        vnf_servers.append(chosen_node)

        # build path to server node
        if chosen_node != current:
            path = create_path(manager.network.G, current, chosen_node, 5)
            full_path.extend(path[1:])

        current = chosen_node

    # build path to destination
    dest = choose_close_node(current, manager.network.switch_nodes, distances)
    path = create_path(manager.network.G, current, dest, 5)
    full_path.extend(path[1:])

    # create request and corresponding SFC
    req = Request(-1, arrival, st, dest, Fr, 0.0, 0.0)
    sfc = SFC(req, start)
    sfc.route_nodes = full_path
    sfc.F_nodes = vnf_servers

    # assign request bandwidth and delay values
    min_delay = manager.get_delay(sfc)
    max_bw = bandwidth[1]

    edge_cnt = defaultdict(int) #count if go through (u,v) > 1 times 
    for u, v in zip(full_path[:-1], full_path[1:]):
        edge_cnt[frozenset([u, v])] += 1
    for key, value in edge_cnt.items():
        u, v = key
        max_bw = min(max_bw, manager.network.remaining_bandwidth(u, v) / value)
    if max_bw < bandwidth[0]:
        return
    req.dr = start - arrival + min_delay * random.uniform(delay_ratio[0], delay_ratio[1])
    req.br = random.uniform(bandwidth[0], max_bw)

    return sfc


def generate_requests(scheme: str, manager: Manager, time=50, arrival_rate=10,
                      segments=(0.5, 0.3, 0.2), bandwidth=(0, 5), delay_ratio=(1, 2)):
    all_requests = []
    arrival_counts = np.random.poisson(arrival_rate, time)
    arrivals = [t for t in range(time) for _ in range(arrival_counts[t])]
    starts = arrivals + scipy.stats.expon.rvs(loc=0, scale=1, size=len(arrivals)).astype(int)

    # tasks = []

    distances = dict(nx.all_pairs_shortest_path_length(manager.network.G))
    # if scheme == 'hard':
    #     for arr, st in zip(arrivals, starts):
    #         sfc = create_feasible_sfc(manager, arr, st, segments,
    #                                   bandwidth, delay_ratio, distances)
    #         if sfc is None:
    #             return
    #         all_requests.append(sfc.request)
    #     # if history:
    #     #     return all_requests, tasks
    #     return all_requests
    random_rate = 0
    if scheme == 'easy':
        random_rate = 0.0
    elif scheme == 'normal':
        random_rate = 0.5
    elif scheme == 'hard':
        random_rate = 1.0

    timeline = defaultdict(list)
    lifetime = np.max(starts)
    for arr, st in zip(arrivals, starts):
        timeline[st].append(arr)
    base_manager = deepcopy(manager)

    idx = 0
    for st in range(lifetime):
        manager.advance()
        reqs = []
        for arr in timeline[st]:
            if random.random() < random_rate:
                sfc = create_feasible_sfc(base_manager, arr, st, segments,
                                          bandwidth, delay_ratio, distances)
            else:
                sfc = create_feasible_sfc(manager, arr, st, segments,
                                          bandwidth, delay_ratio, distances)
                if sfc is None:
                    return
                # manager.operations.append(sfc)
                manager.deploy(sfc)
            sfc.request.idx = idx
            idx += 1
            reqs.append(sfc.request)
        all_requests.extend(reqs)
    #     if history:
    #         tasks.append([sfc for _, _, sfc in manager.operations])
    # if history:
    #     return all_requests, tasks
    return all_requests


if __name__ == '__main__':
    topology = 'cogent'
    server_distribution = 'center'
    scheme = 'easy'

    G = file_to_graph(f'../../data/topology/{topology}_nodes.csv',
                      f'../../data/topology/{topology}_edges.txt')

    network = generate_network(G, server_distribution,
                               [30, 50], [30, 50], [30, 50], [80, 120],
                               [100, 200], [50, 100], [10, 30], [0.1, 0.5])

    VNFs = generate_vnf(network, scheme, server_distribution, 10,
                        [0.1, 0.2], [0.1, 0.2], [0.1, 0.2], [0.1, 1])

    manager = Manager(network, VNFs)

    requests = generate_requests(scheme, manager)
    # save requests to file
    test_export(f'../../data/requests/{topology}_{server_distribution}_{scheme}.txt', manager, requests)