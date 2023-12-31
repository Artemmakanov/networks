from utils import *

import time
from collections import defaultdict
import itertools
from tqdm import tqdm

import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib import animation
import random


# alphabet = 'abcdefghijklmnopqrstuvwxyz'+'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
alphabet = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
alphabet += 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'  

def gen_nodes(num, verbose):
    

    variants = [f'{a}{b}' for a, b in itertools.product(alphabet, alphabet)]
    lst = []
    for _ in tqdm(range(num), leave=verbose):
        new = random.choice(variants)
        lst += [new]
        variants = list(set(variants) - set(new))

    return lst


def gen_pair_of_nodes(variants):
    local = random.choice(variants)
    
    remote = random.choice(list(set(variants) - set(local)))
    return local, remote

def gen_cost():   
    return random.choice([10, 100, 1000, 10000])




def find_convergence(num_nodes,
        num_edges,
        max_steps,
        verbose=False,
        edgeid=None,
        rstp=True,
        FORWARD_DELAY=5,
        log=False,
        root_in_center=False,
        radius=False):

    assert num_nodes * (num_nodes - 1) / 2 >= num_edges

    nodes_data = []
    nodes = gen_nodes(num_nodes, verbose)
    for node in nodes:
        nodes_data += [(node, (random.choice('12'), str(random.choice(range(1000)))))]

    port_list = defaultdict(int)

    edges_data = []

    all_pairs_of_nodes = list(itertools.combinations(nodes, 2))

    ids = list(range(len(all_pairs_of_nodes)))
    random.shuffle(ids)
    # print(all_pairs_of_nodes)
    for i in range(num_edges):
        local, remote = all_pairs_of_nodes[ids[i]]

        cost = gen_cost()
        port_local = port_list[local]
        port_remote = port_list[remote]

        edges_data += [((local, port_local), (remote, port_remote), cost)]

        port_list[local] += 1
        port_list[remote] += 1
        
    net = Network(rstp=rstp, FORWARD_DELAY=FORWARD_DELAY)  

    nodes = {}  

    for label, (priority, mac) in nodes_data:
        nodes[label] = priority + mac

    for s, d, speed in edges_data:

        src_node = s[0]
        src_port = s[1]
        dst_node = d[0]
        dst_port = d[1]

        g1 = net.getBridge(src_node, nodes[src_node])
        g2 = net.getBridge(dst_node, nodes[dst_node])
        net.connect(g1, src_port, g2, dst_port, speed)    

    for br in net.getAllBridges():
        br.launch()

    G, _, _, _ = net.drawG()

    deg_centrality = nx.degree_centrality(G)
    if root_in_center:
        root_node_bid = sorted(deg_centrality.items(), key=lambda x: -x[1])[0][0]
        # for br in net.bridges:
        #     if br.bid == root_node_bid:
        #         br.bid = '9' + br.bid[1:]
        new_bid = '0' + net.bridges[root_node_bid].bid[1:]
        node = net.bridges[root_node_bid]
        del net.bridges[root_node_bid]
        node.bid = new_bid
        net.bridges[new_bid] = node


    plt.close()

    subgraph_dim = None
    subgraph_rad = None
    nb_nodes = G.number_of_nodes()
    while not subgraph_dim and not subgraph_rad and nb_nodes >= 2:
        nb_nodes -= 1
        for SG in (G.subgraph(selected_nodes) for selected_nodes in itertools.combinations(G, nb_nodes)):
            # print(nb_nodes)
            if nx.is_connected(SG):
                subgraph_dim = nx.diameter(SG)
                subgraph_rad = nx.radius(SG)
                break
    
    cutted = False
    for step in tqdm(range(max_steps), leave=verbose):

        net.evolvs(False)
        for br in net.getAllBridges():
            br.processBPDUs(net)
        for br in net.getAllBridges():
            br.sendBPDUs(net)
            if log:
                print(f"Timestep = {step}")
                br.reportSTP()

        if step and not net.evolving:          
            if verbose:
                print(f'STOPPED! at {step}')
            # return net, step, subgraph_dim
            if edgeid is None:
                if radius:
                    return net, step, subgraph_dim, subgraph_rad
                else:
                    return net, step, subgraph_dim
            
            elif not cutted:
                cutted = True
                convergence_1 = step
                subgraph_dim_1 = subgraph_dim
                
                net.cut_edge(onbids=False, edgeid=edgeid)
            else:
                return net, convergence_1, subgraph_dim_1, step, subgraph_dim
                
    
        

def draw_stp(net, name_file,
        steps_convergence,
        broke_time=None,
        bid1=None, 
        bid2=None, 
        edgeid=None):
        
    for br in net.getAllBridges():
        br.launch()

    def simple_update(step, ax):
        ax.clear()

        G, positions, edge_labels, colors = net.drawG()
        nx.draw_networkx_edge_labels(
                G, positions,
                edge_labels=edge_labels,
                ax=ax,
                alpha=0.5)
        nx.draw(G, pos=positions, ax=ax, edge_color=colors)

        ax.set_title("Frame {}".format(step))
        
        net.evolvs(False)

        if broke_time and step == broke_time:
            if edgeid:
                net.cut_edge(onbids=False, edgeid=edgeid)
            elif bid1 and bid2:
                net.cut_edge(onbids=True, bid1=bid1, bid2=bid2)
            

        for br in net.getAllBridges():
            br.processBPDUs(net)
            # print(br.best_bpdu)

        for br in net.getAllBridges():
            br.sendBPDUs(net)


    # Build plot
    fig, ax = plt.subplots(figsize=(7,7))

    ani = animation.FuncAnimation(fig, simple_update, 
                                  frames=steps_convergence + 1,
                                  interval=1000, fargs=(ax, ))
    
    ani.save(f'{name_file}.gif')