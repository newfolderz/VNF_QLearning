import random

import networkx as nx
import numpy as np

from simulation.generator.graph_gen import file_to_graph
from simulation.network_manager import VNF
from simulation.network import Network


def select_server_nodes(graph: nx.Graph, server_distribution):
    node_list = list(graph.nodes)
    node_list.sort(key=lambda node: -len(list(graph.neighbors(node)))) # decrease degree of node 

    if server_distribution == 'uniform':
        server_nodes = random.sample(node_list, int(0.3 * len(node_list))) 
    elif server_distribution == 'urban':
        server_nodes = node_list[:int(0.3 * len(node_list))] # 30% nodes have highest deg 
    elif server_distribution == 'rural':
        server_nodes = node_list[int(0.7 * len(node_list)):] # 30% nodes have lowest deg 
    elif server_distribution == 'centers':
        server_nodes = node_list[:int(0.1 * len(node_list))] # 90% nodes have lowest deg
    else:
        raise Exception('Invalid MDC distribution script!')

    return node_list, server_nodes


def generate_network(graph: nx.Graph, server_distribution: str,
                     cpu: list, ram: list, hdd: list, bandwidth: list,
                     cpu_cost, ram_cost, hdd_cost, delay):
    network = Network()

    # generate device costs and MDC nodes
    node_list, server_nodes = select_server_nodes(graph, server_distribution)
    for node in node_list:
        if node in server_nodes:
            params = {}
            for name, res_range in [('cpu', cpu), ('ram', ram), ('hdd', hdd),
                                    ('cpu_cost', cpu_cost), ('ram_cost', ram_cost), ('hdd_cost', hdd_cost),
                                    ('delay', delay)]:
                cap = random.uniform(res_range[0], res_range[1])
                params[name] = cap
            network.add_server_node(node, **params)
        else:
            network.add_switch_node(node)

    # generate link bandwidth
    max_distance = max(nx.get_edge_attributes(graph, 'distance').values())
    for u, v in graph.edges:
        cap = random.uniform(bandwidth[0], bandwidth[1])
        delay = 0.3 * graph[u][v]['distance'] / max_distance
        network.add_link(u, v, cap, delay)

    return network


def generate_vnf(network: Network, scheme: str,
                 server_distribution: str, vnf_cnt: int,
                 cpu: list, ram: list, hdd: list,
                 delay_range: list):
    vnfs = []
    limits = {}
    for res in ['cpu', 'ram', 'hdd']:
        limits[res] = max([network.G.nodes[node][f'{res[0]}_cap'] for node in network.server_nodes])

    for _ in range(vnf_cnt):
        params = {}
        for name, res_range in [('cpu', cpu), ('ram', ram), ('hdd', hdd)]:
            mean = (res_range[0] + res_range[1])
            std = (res_range[1] - res_range[0]) / 2 # hoi cham 
            cap = random.gauss(mean, std)
            params[name] = max(0, min(cap, limits[name]))
        # if scheme == 'easy':
        params['delay'] = {node: random.uniform(delay_range[0], delay_range[1]) for node in network.server_nodes}
        # else:
        #     params['delay'] = {node: 1000 for node in network.server_nodes}
        vnfs.append(VNF(**params))

    # if scheme == 'easy':
    return vnfs

    # if server_distribution == 'rural':
    #     extra_vnf_nodes = np.random.choice(network.server_nodes, vnf_cnt)
    #     for vnf, node in zip(vnfs, extra_vnf_nodes):
    #         vnf.df[node] = random.uniform(delay_range[0], delay_range[1])
    #     for node in network.server_nodes:
    #         if min([vnf.df[node] for vnf in vnfs]) == 1000:
    #             np.random.choice(vnfs).df[node] = random.uniform(delay_range[0], delay_range[1])
    # elif server_distribution == 'centers':
    #     for vnf in vnfs:
    #         vnf.df = {node: dl for node, dl in
    #                   zip(network.server_nodes, np.random.uniform(delay_range[0], delay_range[1],
    #                                                               len(network.server_nodes)))}
    # else:
    #     for node in network.server_nodes:
    #         cnt = int(vnf_cnt * np.random.uniform(0.1, 0.2))
    #         for _ in range(cnt):
    #             np.random.choice(vnfs).df[node] = random.uniform(delay_range[0], delay_range[1])
    #     extra_vnf_nodes = np.random.choice(network.server_nodes, vnf_cnt)
    #     for vnf, node in zip(vnfs, extra_vnf_nodes):
    #         vnf.df[node] = random.uniform(delay_range[0], delay_range[1])
    #
    # return vnfs


if __name__ == '__main__':
    # # graph = generate_graph(10, 0.3)
    # # graph_to_file(graph, './data/graph.txt')
    # datasets = ['nsf', 'cogent', 'conus']
    # distributions = ['uniform', 'urban', 'rural', 'centers']
    #
    # for dataset in datasets:
    #     graph = file_to_edges2(f'../data/topology/{dataset}_edges.txt')
    #     for dist in distributions:
    #         for i in range(5):
    #             if dataset == 'nsf':
    #                 network = generate_network(graph, dist, 100, 100, 100, 5)
    #             else:
    #                 network = generate_network(graph, dist, 100, 100, 100, 10)
    #             network_to_file(network, f'../data/input/{dataset}_{dist}_{i}_network.txt')
    # network = file_to_network(f'./data/{dataset}_nodes.csv')
    # network.visualize(pos_path=f'./data/{dataset}_nodes.csv')

    topology = 'nsf'
    server_distribution = 'uniform'
    scheme = 'easy'
    G = file_to_graph(f'../../data/topology/{topology}_nodes.csv',
                      f'../../data/topology/{topology}_edges.txt')
    network = generate_network(G, server_distribution,
                               [30, 50], [30, 50], [30, 50], [80, 120],
                               [100, 200], [50, 100], [10, 30], [0.1, 0.5])
    print(network.G.nodes.data())
    print(network.G.edges.data())
    VNFs = generate_vnf(network, scheme, server_distribution, 10,
                        [1, 5], [1, 5], [1, 5], [0.1, 1])
    for vnf in VNFs:
        print(vnf.df)
