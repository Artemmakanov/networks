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


alphabet = 'abcdefghijklmnopqrstuvwxyz'+'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
alphabet += 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
alphabet += 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'  

def gen_nodes(num):

    variants = [f'{a}{b}' for a, b in itertools.product(alphabet, alphabet)]
    lst = []
    for _ in range(num):
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

def find_convergence_msti(
        msti,
        nodes_data,
        edges_data,
        max_steps,
        bridge2region,
        bridge2vlan,
        msti2vlan,
        edgeid=None,
        rstp=True,
        verbose=False):
   
    net = Network(rstp=rstp, bridge2vlan=bridge2vlan, vlans=msti2vlan[msti])  

    nodes = {}  

    for label, (priority, mac) in nodes_data:
        nodes[label] = priority + mac

    for s, d, speed in edges_data:

        src_node = s[0]
        src_port = s[1]
        dst_node = d[0]
        dst_port = d[1]
        revision_level = 0
        
        g1 = net.getBridge(src_node, nodes[src_node], bridge2region[nodes[src_node][1:]], revision_level, msti) 
        g2 = net.getBridge(dst_node, nodes[dst_node], bridge2region[nodes[dst_node][1:]], revision_level, msti)
        net.connect(g1, src_port, g2, dst_port, speed)    

    for br in net.getAllBridges():
        br.launch()

    G, _, _, _, _ = net.drawG()
    plt.close()

    subgraph_dim = None
    nb_nodes = G.number_of_nodes()
    while not subgraph_dim and nb_nodes >= 2:
        nb_nodes -= 1
        for SG in (G.subgraph(selected_nodes) for selected_nodes in itertools.combinations(G, nb_nodes)):
            # print(nb_nodes)
            if nx.is_connected(SG):
                subgraph_dim = nx.diameter(SG)
                break
    
    cutted = False
    for step in tqdm(range(max_steps), leave=verbose):

        net.evolvs(False)
        for br in net.getAllBridges():
            br.processBPDUs(net)
        for br in net.getAllBridges():
            br.sendBPDUs(net)

        if step and not net.evolving:          
            if verbose:
                print(f'STOPPED! at {step}')
            if edgeid is None:
                return net, step, subgraph_dim
            
            elif not cutted:
                cutted = True
                convergence_1 = step
                subgraph_dim_1 = subgraph_dim
                
                net.cut_edge(onbids=False, edgeid=edgeid)
            else:
                return net, convergence_1, subgraph_dim_1, step, subgraph_dim
                
    assert 'TIME LIMIT!'

def find_convergence(
        num_nodes,
        num_edges,
        max_steps,
        vlans_n,
        trees_n,
        regions_n,
        verbose=False,
        edgeid=None,
        rstp=True):

    assert num_nodes * (num_nodes - 1) / 2 >= num_edges
    assert vlans_n > 0
    assert vlans_n >= trees_n
    assert regions_n > 0

    nets, c1s, d1s, c2s, d2s = [], [], [], [], []
    nodes = gen_nodes(num_nodes)
    all_pairs_of_nodes = list(itertools.combinations(nodes, 2))

    ids = list(range(len(all_pairs_of_nodes)))
    random.shuffle(ids)
    # print(all_pairs_of_nodes)
    
    msti2vlan = defaultdict(list)
    for id in range(trees_n):
        msti2vlan[id] += [id]
    for vlan in range(trees_n, vlans_n):
        msti2vlan[random.choice(list(msti2vlan.keys()))] += [vlan]
    
    mac_data = []
    for node in nodes:
        mac_data += [(node, str(random.choice(range(1000))))]

    region2bridge =  defaultdict(list)
    for id in range(regions_n):
        _, mac = mac_data[id]
        region2bridge[id] += [mac]
    for id in range(regions_n, num_nodes):
        _, mac = mac_data[id]
        region2bridge[random.choice(list(region2bridge.keys()))] += [mac]

    bridge2region = {}
    for region, lst in region2bridge.items():
        for v in lst:
            bridge2region[v] = region

    vlan2mac =  defaultdict(list)
    for id in range(vlans_n):
        _, mac = mac_data[id]
        vlan2mac[id] += [mac]
    for id in range(vlans_n, num_nodes):
        _, mac = mac_data[id]
        vlan2mac[random.choice(list(vlan2mac.keys()))] += [mac]
        
    for msti, vlans in msti2vlan.items():
        # будем считать, что в каждом VLAN одного дерева
        # мост имеет одинаковый приоритет
        nodes_data = []
        bridge2vlan = defaultdict(list)
        for node, mac in mac_data:
            bid = (node, (random.choice('012'), mac))
            nodes_data += [bid]
            t = random.choice(range(len(vlan2mac)))
            bridge2vlan["".join(bid[1])] += list(vlan2mac.keys())[:t+1]
        

        # print(bridge2vlan)
        edges_data = []
        port_list = defaultdict(int)
        for i in range(num_edges):
            local, remote = all_pairs_of_nodes[ids[i]]
            cost = gen_cost()
            port_local = port_list[local]
            port_remote = port_list[remote]
            # будем считать, что мы выбрали самый маленькй cost из тех линков
            # что есть между двумя коммутаторами
            edges_data += [((local, port_local), (remote, port_remote), cost)]
            port_list[local] += 1
            port_list[remote] += 1
            
        output = find_convergence_msti(
            msti,
            nodes_data,
            edges_data,
            max_steps,
            bridge2region,
            bridge2vlan,
            msti2vlan,
            verbose=verbose,
            edgeid=edgeid,
            rstp=rstp)
        
        if edgeid is None:
            net, c1, d1 = output
            nets.append(net)
            c1s.append(c1)
            d1s.append(d1)
        else:
            net, c1, d1, c2, d2 = output
            nets.append(net)
            c1s.append(c1)
            d1s.append(d1)
            c2s.append(c2)
            d2s.append(d2)

    if edgeid is None:
        return nets, msti2vlan, region2bridge, c1s, d1s
    else:
        return nets, msti2vlan, region2bridge, c1s, d1s, c2s, d2s

def draw_stp(
        nets,
        msti2vlan,
        region2bridge,
        name_file,
        steps_convergence,
        broke_times=None,
        bid1=None, 
        bid2=None, 
        edgeid=None
        ):

    def simple_update(step, ax):
        ax.clear()

        G, positions, edge_labels, edge_color, node_color = net.drawG()
        nx.draw_networkx_edge_labels(
                G, positions,
                edge_labels=edge_labels,
                ax=ax)
        nx.draw(G, pos=positions, ax=ax, edge_color=edge_color, node_color=node_color)
        
        vlans_str = " ".join([ str(vlan) for vlan in vlans])
        ax.set_title(f"Tree {msti} Vlans {vlans_str} Frame {step}")
        
        net.evolvs(False)
        
        if broke_times:
            broke_time = broke_times[msti] + 1
            if step == broke_time:
                if edgeid:
                    net.cut_edge(onbids=False, edgeid=edgeid)
                elif bid1 and bid2:
                    net.cut_edge(onbids=True, bid1=bid1, bid2=bid2)
                
        for br in net.getAllBridges():
            br.sendBPDUs(net)
        for br in net.getAllBridges():
            br.processBPDUs(net)
            # print(br.best_bpdu)

        

    for msti, vlans in msti2vlan.items():
        net = nets[msti]
        for br in net.getAllBridges():
            br.launch()
        # Build plot
        fig, ax = plt.subplots(figsize=(20,20))
        plt.title(msti)
        ani = animation.FuncAnimation(fig, simple_update, 
                                    frames=steps_convergence + 1,
                                    interval=1000, fargs=(ax, ))
        
        ani.save(f'{name_file}_vlan-{msti}.gif')