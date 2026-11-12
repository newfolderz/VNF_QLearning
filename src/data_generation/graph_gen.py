from collections import defaultdict
from string import ascii_uppercase
import random
import os

import networkx as nx
import numpy as np
import pandas as pd

alphabet = list(ascii_uppercase)


def id_to_name(node_id: int):
    if node_id < 26:
        return alphabet[node_id]
    return alphabet[node_id//26-1] + alphabet[node_id%26]


def generate_graph(nodes, density):
    edge_set = set()
    components = {}

    for i in range(nodes):
        components[i] = [i]

    while len(components) > 1:
        com1, com2 = random.sample([*components.keys()], 2)
        a = random.choice(components[com1])
        b = random.choice(components[com2])

        edge_set.add(frozenset([a, b]))
        components[com1].extend(components[com2])
        components.pop(com2, None)

    full_edges = int(nodes * (nodes-1) / 2)
    for _ in range(len(edge_set), int(density * full_edges)):
        a = b = -1
        while a == b or frozenset([a, b]) in edge_set:
            a = random.randint(0, nodes-1)
            b = random.randint(0, nodes-1)
        edge_set.add(frozenset([a, b]))

    edge_list = []
    for edge in edge_set:
        a, b = edge
        edge_list.append((id_to_name(a), id_to_name(b)))

    return edge_list


def graph_to_file(edge_list, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(str(len(edge_list)) + '\n')
        for a, b in edge_list:
            f.write(a + ' ' + b + '\n')


def file_to_edges(path):
    with open(path) as f:
        m = int(f.readline())
        edges = []
        for _ in range(m):
            u, v = f.readline().split()
            edges.append([u, v])
    return edges


def file_to_edges2(path):
    with open(path) as f:
        edges = []
        line = f.readline()
        while line:
            if len(line) < 3:
                break
            u, v, _ = line.split()
            edges.append([u, v])
            line = f.readline()
    return edges


def file_to_adjacency_list(path):
    with open(path) as f:
        m = int(f.readline())
        adj_list = defaultdict(list)
        for _ in range(m):
            u, v = f.readline().split()
            adj_list[u].append(v)
            adj_list[v].append(u)
    return adj_list


def file_to_graph(node_path, edge_path):
    G = nx.Graph()
    df = pd.read_csv(node_path, skiprows=1)
    pos_nodes = df.to_numpy()
    for i in range(pos_nodes.shape[0]):
        G.add_node(i)
    with open(edge_path) as f:
        line = f.readline()
        while line:
            if len(line) < 3:
                break
            u, v, _ = line.split()
            u, v = int(u), int(v)
            G.add_edge(u, v, distance=np.sqrt(np.sum(np.square(pos_nodes[u] - pos_nodes[v]))))
            line = f.readline()
    return G


if __name__ == '__main__':
    # graph = generate_graph(20, 0.3)
    # graph_to_file(graph, './data/graph.txt')

    G = file_to_graph('../../data/topology/nsf_nodes.csv',
                      '../../data/topology/nsf_edges.txt')
    print(G.edges.data())
