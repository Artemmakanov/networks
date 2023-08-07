from typing import Any, List
import pickle

import networkx as nx

class BPDU():
    def __init__(self, 
        root_bid: str,
        rpc: int,
        sender_bid: int,
        send_port_id: str):

        self.root_bid = root_bid
        self.rpc = rpc
        self.sender_bid = sender_bid
        self.send_port_id = send_port_id

    def getBest(self, other):
   
        """
        Из двух BPDU кадров выбирается наименьший. Сраниваются поля в
        следующеи порядке:
        1. Root bridge id
        2. Root path cost
        3. Sender bridge id
        4. Sender port id
        """

        if not other:
            return self

        _bpdu = (self.root_bid, self.rpc, self.sender_bid, self.send_port_id)
        
        _bpdu_other = (other.root_bid, other.rpc, other.sender_bid, other.send_port_id)
        
        return self if _bpdu <= _bpdu_other else other


    def __repr__(self) -> str:
        return f"[{self.root_bid}, {self.rpc}, {self.sender_bid}, {self.send_port_id}]"


class Port():
    """
    Порт коммутатора
    """

    ROLE_ROOT = "Root Port"
    ROLE_UNDESG = "Undesignated"
    ROLE_DESG = "Designated"

    ST_FORWARD = "Forwarding"
    ST_BLOCKED = "Blocked"

    ROLE_STATUS_MAP = {
        ROLE_ROOT: ST_FORWARD,
        ROLE_DESG: ST_FORWARD,
        ROLE_UNDESG: ST_BLOCKED
    }
    
    def __init__(self, id, cost):
        self.id = id
        self.cost = cost
        self.remote_port = None
        self.resetSTP()

    def resetSTP(self) -> None:
        self.best_bpdu = None
        self.role = Port.ROLE_UNDESG
        self.status = Port.ST_BLOCKED
        self.rpc = None

    def setRemote(self, remote)-> None:
        self.remote_port = remote

    def sendBPDU(self, b: BPDU)-> None:
        # сохраняем superior BPDU
        self.best_bpdu = self.best_bpdu.getBest(b) if self.best_bpdu else b
        self.remote_port.receiveBPDU(b)

    def receiveBPDU(self, b: BPDU)-> None:
        # сохраняем superior BPDU
        self.best_bpdu = self.best_bpdu.getBest(b) if self.best_bpdu else b

    def setRole(self, role: str)-> None:
        # обновление роли и статуса
        self.role = role
        self.status = self.ROLE_STATUS_MAP[role]

    def __repr__(self):
        return f"{self.id} {self.status}"



class Bridge():
    """
    Коммутатор
    """

    def __init__(self, name: str, bid: str):
        self.name = name
        self.bid = bid
        self.root_bid = self.bid
        self.ports = []
        

    def launch(self) -> None:
        """
        Когда коммутатор подключается к сети, он думает - что он
        корневой, и посылает стратовый BPDU на каждый порт
        """

        self.best_bpdu = BPDU(self.bid, 0, self.bid, 0)
        self.root = True
        self.root_port = None

        for port in self.ports:
            port.resetSTP()

    def processBPDUs(self, net) -> None:
        """
        Коммутатор генерирует новый пакет BPDU, основываясь на данных 
        из предыдущего BPDU. Если новый BPDU является superior по 
        отношению BPDU, который коммутатор получил на порту, он
        передаст новый BPDU, иначе он больше не будет передавать 
        BPDU на этот порт. Этот порт будет либо root, либо 
        blockes. Другие порты являются designated. Коммутатор
        продолжит посылать BPDU на эти порты и передавать пакеты
        данных.
        """

        

        # Создаем на каждый порт по BPDU, каждое BPDU рассчитывается 
        # на основе наименьшего BPDU и цены интерфейса, и id порта.
        best = [BPDU(port.best_bpdu.root_bid, port.best_bpdu.rpc + \
                     port.cost, self.bid, port.id) for port in self.ports if port.best_bpdu]

        # Выбор наименьшего BPDU между всеми портами
        best_bpdu = BPDU(self.bid, 0, self.bid, 0)
        root_port = None
        for b in best:
            if b.getBest(best_bpdu) == b:
                best_bpdu = b
                root_port = b.send_port_id


        # if self.best_bpdu != best_bpdu:
        #     net.evolvs(True)
        # self.best_bpdu = best_bpdu
        if (best_bpdu.root_bid, best_bpdu.rpc, best_bpdu.sender_bid) != \
            (self.best_bpdu.root_bid, self.best_bpdu.rpc, self.best_bpdu.sender_bid):
            net.evolvs(True)
            # print(best_bpdu)
            # print(self.best_bpdu)
            # print('BDPU changed')
            
        self.best_bpdu = best_bpdu

        if self.root_port != root_port:
            net.evolvs(True)
            # print('root_port')

        self.root_port = root_port

        new_root = self.best_bpdu.root_bid == self.bid
        if new_root != self.root:
            net.evolvs(True)
            # print('root')

        self.root = new_root

        new_root_bid = self.best_bpdu.root_bid
        if new_root_bid != self.root_bid:
            net.evolvs(True)
            # print('root_bid')

        self.root_bid = new_root_bid
        

    def sendBPDUs(self):
        
        if self.root:
            
            for port in self.ports:
                self.best_bpdu.send_port_id = port.id
                port.sendBPDU(self.best_bpdu)
                port.setRole(Port.ROLE_DESG)
 
        else:
            for port in self.ports:
               
                if self.best_bpdu.getBest(port.best_bpdu) == self.best_bpdu:
          
                    port.sendBPDU(self.best_bpdu)
                    port.setRole(Port.ROLE_DESG)
                    port.rpc = None

                elif port.id == self.root_port:
                    port.rpc = self.best_bpdu.rpc
                    port.setRole(Port.ROLE_ROOT)
                else:
                    port.rpc = None
                    port.setRole(Port.ROLE_UNDESG)


class Network():

    COST_MAP = {
        10: 100,
        100: 19,
        1000: 4,
        10000: 2
    }

    def __init__(self):
        self.bridges = {}
        self.edges = []
        self.evolving = None

    def evolvs(self, evolvs):
        self.evolving = evolvs


    def getBridge(self, name, bid):
        if bid in self.bridges:
            return self.bridges[bid]
        br = Bridge(name, bid)
        self.bridges[bid] = br
        return br

    def getAllBridges(self):
        return self.bridges.values()

    def connect(self, br1, port1, br2, port2, speed):
        local = Port(port1, self.COST_MAP[speed])
        remote = Port(port2, self.COST_MAP[speed])
        local.setRemote(remote)
        remote.setRemote(local)
        br1.ports.append(local)
        br2.ports.append(remote)

        self.edges += [(br1, br2, local, remote, self.COST_MAP[speed])]

    def drawG(self):

        G = nx.Graph()
        G.add_edges_from([(br1.bid, br2.bid) for br1, br2, _, _, _ in self.edges])

   
        positions = nx.kamada_kawai_layout(G, scale=3) #seed
        edge_labels = {}
    
        for edge in self.edges:
            br1, br2, local, remote, cost = edge

            edge_labels[(br1.bid, br2.bid)] = cost


            if local.status == 'Blocked' or remote.status == 'Blocked':
                G.edges[br1.bid, br2.bid]['color'] = 'r'
            else:
                G.edges[br1.bid, br2.bid]['color'] = 'b'
                               
        labels = {bid : f"{self.bridges[bid].name}\n{self.bridges[bid].root_bid}\n{self.bridges[bid].best_bpdu.rpc}" for bid in positions.keys()}

        nx.draw_networkx_labels(G, positions, labels=labels)

        _,colors = zip(*nx.get_edge_attributes(G,'color').items())


        return G, positions, edge_labels, colors



    def save(self, name):
        with open(name, 'wb') as handle:
            pickle.dump((self.bridges, self.edges), handle, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, name):
        with open(name, 'rb') as handle:
            self.bridges, self.edges = pickle.load(handle)

    def __repr__(self):
        return ",".join(map(str, self.bridges.keys()))
    

    















