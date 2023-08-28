from typing import Any, List
import pickle

import numpy as np
import networkx as nx

TC_PAUSE = 3
FORWARD_DELAY = 2

class frameBPDUMST():
    def __init__(self,
        root_bid: str,
        external_rpc: int,
        region_root_bid: str,
        internal_rpc: int,
        bid: str,
        send_port_id: int,
        recv_port_id: int
        ):

        self.root_bid = root_bid
        self.external_rpc = external_rpc
        self.region_root_bid = region_root_bid
        self.internal_rpc = internal_rpc
        self.bid = bid
        self.send_port_id = send_port_id
        self.recv_port_id = recv_port_id

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
         
        _bpdu = (self.root_bid, self.external_rpc, self.region_root_bid, \
                self.internal_rpc, self.bid, self.send_port_id, self.recv_port_id)
        _bpdu_other = (other.root_bid, other.external_rpc, other.region_root_bid, \
                other.internal_rpc, other.bid, other.send_port_id, other.recv_port_id)
        
        return self if _bpdu <= _bpdu_other else other

    def __repr__(self) -> str:
        return f"{self.root_bid}, {self.external_rpc}, {self.region_root_bid}, {self.internal_rpc}, {self.bid}, {self.send_port_id}"
    
    def __str__(self) -> str:
        return f"{self.root_bid}, {self.external_rpc}, {self.region_root_bid}, {self.internal_rpc}, {self.bid}, {self.send_port_id}"

    def tostp(self):
        b = frameBPDUSTP(self.root_bid, self.external_rpc, self.bid, self.send_port_id)
        return b
    
    def tomst(self, *args):
        return self
    
class frameBPDUSTP():
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
        
        if type(other) != frameBPDUSTP:
            other = other.tostp()
        _bpdu = (self.root_bid, self.rpc, self.sender_bid, self.send_port_id)
        _bpdu_other = (other.root_bid, other.rpc, other.sender_bid, other.send_port_id)
        return self if _bpdu <= _bpdu_other else other


    def __repr__(self) -> str:
        return f"[{self.root_bid}, {self.rpc}, {self.sender_bid}, {self.send_port_id}]"
    
    def __str__(self) -> str:
        return f"[{self.root_bid}, {self.rpc}, {self.sender_bid}, {self.send_port_id}]"

    def tomst(self, recv_port_id):
        b = frameBPDUMST(self.root_bid, self.rpc, self.sender_bid, 0, self.sender_bid, self.send_port_id, recv_port_id)
        return b
    def tostp(self):
        return self



class Port():
    """
    Порт коммутатора
    """
  
    ROLE_STATUS_MAP_STP = {
        "Root Port": {
            "Blocked": "Listening",
            "Listening": "Learning",
            "Learning": "Forwarding",
            "Forwarding": "Forwarding"
        },
        "Designated": {
            "Blocked": "Listening",
            "Listening": "Learning",
            "Learning": "Forwarding",
            "Forwarding": "Forwarding"
        },
        "Undesignated": "Blocked"
    }

    ROLE_STATUS_MAP_RSTP = {
        "Root Port": {
            "Blocked": "Learning",
            "Learning": "Forwarding",
            "Forwarding": "Forwarding"
        },
        "Designated": {
            "Blocked": "Learning",
            "Learning": "Forwarding",
            "Forwarding": "Forwarding"
        },
        "Undesignated": "Blocked"
    }
    
    def __init__(self, id, cost, rstp, mst, FORWARD_DELAY):
        self.id = id
        self.cost = cost
        self.remote_port = None
        self.region_root = True
        self.root = True
        self.broken = False
        self.rstp = rstp
        self.mst = mst
        self.FORWARD_DELAY = FORWARD_DELAY
        self.resetSTP()
             
    def resetSTP(self) -> None:
        self.best_bpdu = None
        self.role = "Undesignated"
        self.status = "Blocked"
        self.rpc = None
        self.timer = self.FORWARD_DELAY

    def setRemote(self, remote) -> None:
        self.remote_port = remote

    def sendBPDU(self, b)-> None:
        # сохраняем superior BPDU
        if self.remote_port.mst:
            self.best_bpdu = self.best_bpdu.getBest(b) if self.best_bpdu else b
            self.remote_port.receiveBPDU(b)
        else:
            if b:
                b = b.tostp()
            if self.best_bpdu:
                self.best_bpdu = self.best_bpdu.tostp()

            self.best_bpdu = self.best_bpdu.getBest(b) if self.best_bpdu else b
            self.remote_port.receiveBPDU(b)

    def receiveBPDU(self, b) -> None:
        # сохраняем superior BPDU
        if self.remote_port.mst:
            self.best_bpdu = self.best_bpdu.getBest(b) if self.best_bpdu else b
        else:
            if self.best_bpdu:
                self.best_bpdu = self.best_bpdu.tostp()
            self.best_bpdu = self.best_bpdu.getBest(b) if self.best_bpdu else b

    def setRole(self, role: str)-> None:
        # обновление роли и статуса
        if self.delay():
            self.role = role
            status = self.ROLE_STATUS_MAP_RSTP[role] if self.rstp else self.ROLE_STATUS_MAP_STP[role]
            self.status = status[self.status] if type(status) == dict else status
            self.timer = self.FORWARD_DELAY
            if self.status in ['Blocked', 'Forwarding']:
                changed = False
            else:
                changed = True

        else:
            changed = True
        return (self.status, changed)
     
    def broke(self):
        self.broken = True

    def delay(self):
        if self.timer > 0:
            self.timer -= 1
        return self.timer == 0

    def __repr__(self):
        return f"{self.id} {self.role} {self.status} {self.mst}"


class Bridge():
    """
    Коммутатор
    """

    def __init__(
            self,
            name: str,
            bid: str,
            region_name: str,
            revision_level: int,
            msti: int):
        
        self.name = name
        self.bid = bid
        self.root_bid = self.bid
        self.boundary = None
        self.ports = []
        self.timer = 0
        self.region_name = region_name
        self.revision_level = revision_level
        self.msti = msti

    def launch(self) -> None:
        """
        Когда коммутатор подключается к сети, он думает - что он
        корневой, и посылает стратовый BPDU на каждый порт
        """

        self.best_bpdu = frameBPDUMST(self.bid, 0, self.bid, 0, self.bid, 0, 0)
        self.root_bid = self.bid
        self.root = True
        self.region_root = True
        self.region_root_bid = self.bid
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
        blocked. Другие порты являются designated. Коммутатор
        продолжит посылать BPDU на эти порты и передавать пакеты
        данных.
        """
        if self.delay():
            # Создаем на каждый порт по BPDU, каждое BPDU рассчитывается 
            # на основе наименьшего BPDU и цены интерфейса, и id порта.
            best = []
            
            for port in self.ports:
                if port.best_bpdu:
                    if type(port.best_bpdu) == frameBPDUMST:
                        b = frameBPDUMST(
                                port.best_bpdu.root_bid,
                                port.best_bpdu.external_rpc + port.cost * int(not port.mst),
                                port.best_bpdu.region_root_bid,
                                port.best_bpdu.internal_rpc + port.cost,
                                self.bid,
                                port.id,
                                port.remote_port.id)
                    else:
                        b = frameBPDUMST(
                                port.best_bpdu.root_bid,
                                port.best_bpdu.rpc + port.cost,
                                self.bid,
                                0,
                                self.bid,
                                port.id,
                                port.remote_port.id) 
                    best += [(b, port)]
   
            # Выбор наименьшего BPDU между всеми портами
            best_bpdu = frameBPDUMST(self.bid, 0, self.bid, 0, self.bid, 0, 0)
            root_port = None
            region_root_port = None
            for b, port in best:
                if b.getBest(best_bpdu) == b:
                    best_bpdu = b
                    root_port = b.send_port_id
                    if not port.mst:
                        region_root_port = port

            if (best_bpdu.root_bid, best_bpdu.external_rpc, best_bpdu.region_root_bid, best_bpdu.internal_rpc, best_bpdu.bid) != \
                (self.best_bpdu.root_bid, self.best_bpdu.external_rpc, self.best_bpdu.region_root_bid, self.best_bpdu.internal_rpc, self.best_bpdu.bid):
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
            # self.region_root_bid = self.best_bpdu.region_root_bid if mst_seen else self.region_root_bid
            self.region_root_bid = self.best_bpdu.region_root_bid
            if region_root_port:
                region_root_port.root = True
                self.region_root_port = region_root_port
                for port in self.ports:
                    if port != region_root_port:
                        port.root = False
            self.region_root = self.region_root_bid == self.bid
            new_root_bid = self.best_bpdu.root_bid

            if new_root_bid != self.root_bid:
                net.evolvs(True)
                # print('root_bid')

            self.root_bid = new_root_bid
            # print(self.root_port)
            # print(self.best_bpdu)
            # print(self.ports)

    def sendBPDUs(self, net) -> None:
        delay =  self.delay()
        port_status_changed = []
        brige_best_bpdu = self.best_bpdu.tostp()
        if self.root:
            for port in self.ports:
                if not port.broken:
                    if delay:
                        self.best_bpdu.send_port_id = port.id
                        port.sendBPDU(self.best_bpdu)
                    if port.mst or not port.mst and port.remote_port.region_root:
                        
                        port_status_changed += [port.setRole("Designated")]
                    else:
                        port.rpc = None
                        port_status_changed += [port.setRole("Undesignated")]
        elif self.region_root:
            for port in self.ports:
                if not port.broken:
                    if port.mst:
                        if delay:
                            self.best_bpdu.send_port_id = port.id
                            port.sendBPDU(self.best_bpdu)
                        port_status_changed += [port.setRole("Designated")]
                    else:
                        if brige_best_bpdu.getBest(port.best_bpdu) == brige_best_bpdu: # port.remote_port.region_root:
                            if delay:
                                port.best_bpdu = port.best_bpdu.tostp() if port.best_bpdu else None
                                port.sendBPDU(self.best_bpdu)
                            port_status_changed += [port.setRole("Designated")]
                        elif port.region_root and port.id == self.root_port:
                            if delay:
                                port.rpc = brige_best_bpdu.rpc
                            port_status_changed += [port.setRole("Root Port")]
                        else:
                            if delay:
                                port.rpc = None
                            port_status_changed += [port.setRole("Undesignated")]
        else:
            for port in self.ports:
                if not port.broken:
                    if port.mst:
                        port_best_bpdu = port.best_bpdu.tomst(port.remote_port.id)
                        # self.best_bpdu = self.best_bpdu.tomst(port.remote_port.id)
                        if self.best_bpdu.getBest(port_best_bpdu) == self.best_bpdu:
                            if delay:
                                port.sendBPDU(self.best_bpdu)
                                port.rpc = None
                            port_status_changed += [port.setRole("Designated")]
                        elif port.id == self.root_port:
                            if delay:
                                port.rpc = self.best_bpdu.external_rpc
                            port_status_changed += [port.setRole("Root Port")]
                        else:
                            if delay:
                                port.rpc = None
                            port_status_changed += [port.setRole("Undesignated")]
                    else:
                        port_best_bpdu = port.best_bpdu.tostp() if port.best_bpdu else None
                        if brige_best_bpdu.getBest(port_best_bpdu) == brige_best_bpdu: # port.remote_port.region_root:
                            if delay:
                                port.sendBPDU(brige_best_bpdu)
                                port.rpc = None
                            port_status_changed += [port.setRole("Designated")]
                        elif port.id == self.root_port:
                            if delay:
                                port.rpc = brige_best_bpdu.rpc
                            port_status_changed += [port.setRole("Root Port")]
                        else:
                            if delay:
                                port.rpc = None
                            port_status_changed += [port.setRole("Undesignated")]

        port_changed = [s[1] for s in port_status_changed]
        port_blocked = [s[0] == 'Blocked' for s in port_status_changed]
        if any(port_changed) or all(port_blocked):
            net.evolvs(True)

    
    def setDelay(self):
        self.timer = TC_PAUSE

    def delay(self):
        if self.timer > 0:
            self.timer -= 1
        return self.timer == 0
    
    def reportSTP(self):
            
        root_id = "Этот мост - root" if self.root else ""
        print(f"BID: {self.bid}. {root_id}")

        row_format = "{:<8} {:<15} {:<15} {:<8}"
        print("-" * 65)
        print(row_format.format('Port', 'Role', 'Status', 'Cost', 'Cost-to-Root'))
        print("-" * 65)
        for p in sorted(self.ports, key=lambda x: x.id):
            print(row_format.format(p.id, p.role, p.status, p.cost))
        print()
        

class Network():

    COST_MAP_STP = {
        10: 100,
        100: 19,
        1000: 4,
        10000: 2
    }

    COST_MAP_RSTP = {
        10: 2000000,
        100: 200000,
        1000: 20000,
        10000: 2000
    }

    def __init__(self, rstp=True, bridge2vlan=None, vlans=None, FORWARD_DELAY=FORWARD_DELAY):
        self.bridges = {}
        self.edges = []
        self.evolving = None
        self.rstp = rstp
        self.bridge2vlan = bridge2vlan
        self.vlans = vlans
        self.FORWARD_DELAY = FORWARD_DELAY

    def evolvs(self, evolvs):
        self.evolving = evolvs

    # def cut_edge(self, onbids=False, bid1=None, bid2=None, edgeid=None):

    #     if onbids:
    #         for edge in self.edges:
    #             br1, br2 = edge[0], edge[1]
    #             if br1.bid in (bid1, bid2) and br2.bid in (bid1, bid2):
    #                 p1, p2 = edge[2], edge[3]
    #     else:
    #         edge = self.edges[edgeid]
    #         br1, br2 = edge[0], edge[1]
    #         p1, p2 = edge[2], edge[3]

    #     p1.sendBPDU(frameBPDUMST(False, self.bid, 0, self.bid, 0, self.bid, 0))
    #     p2.sendBPDU(frameBPDUMST(False, self.bid, 0, self.bid, 0, self.bid, 0))
    #     p1.broke()
    #     p2.broke()
        
        # print('CUTTED!')

    def getBridge(self, name, bid, region_name, revision_level, msti):
        if bid in self.bridges:
            return self.bridges[bid]
        # имея несколько vlan в одном дереве, получаем
        # что вероятность участия моста в соединении с хостами
        # конкретного vlan-а есть вероятность того, что среди 
        # len(vlans) испытания есть хотя бы одно удачное
        # mst = np.random.binomial(1, 0.7, 1)[0] >= 1
        br = Bridge(name, bid, region_name, revision_level, msti)
   
        self.bridges[bid] = br
        return br

    def getAllBridges(self):
        return self.bridges.values()

    def connect(self, br1, port1, br2, port2, speed):
        cost = self.COST_MAP_RSTP[speed] if self.rstp else self.COST_MAP_STP[speed]
        mst = br1.region_name == br2.region_name and \
            br1.revision_level == br2.revision_level and \
            br1.msti == br2.msti 
        
        local = Port(port1, cost, self.rstp, mst, self.FORWARD_DELAY)
        remote = Port(port2, cost, self.rstp, mst, self.FORWARD_DELAY)
        local.setRemote(remote)
        remote.setRemote(local)
        br1.ports.append(local)
        br2.ports.append(remote)
        self.edges += [(br1, br2, local, remote, cost)]

    def drawG(self):
        
        status2c = {
            "Blocked": 'b',
            "Listening": 'li',
            "Learning": 'le',
            "Forwarding": 'f'
        }

        G = nx.Graph()
        G.add_edges_from([(br1.bid, br2.bid) for br1, br2, _, _, _ in self.edges])
        
        positions = nx.kamada_kawai_layout(G, scale=3)
        edge_labels = {}
        for edge in self.edges:
            br1, br2, local, remote, cost = edge
            gap = " "*1
            if local.broken and remote.broken:
                l = 'X'
            else:
                l = f"{status2c[local.status]}" + gap + f"{cost}" + gap + f"{status2c[remote.status]}"
            edge_labels[(br1.bid, br2.bid)] = l

            if local.broken and remote.broken:
                G.edges[br1.bid, br2.bid]['color'] = 'black'
            elif local.status == 'Forwarding' and remote.status == 'Forwarding' and br1.bid != br2.bid:
                G.edges[br1.bid, br2.bid]['color'] = 'blue'
            else:
                G.edges[br1.bid, br2.bid]['color'] = 'red'
           
            
        labels = {bid : f"bid:{bid}\n" + \
                  f"R: {self.bridges[bid].root_bid}\n" + \
                  f"vlan:{self.bridge2vlan[bid] if bid in self.bridge2vlan else 'X'}\n" + \
                  f"RR: {self.bridges[bid].region_root_bid}\n" + \
                  f"E: {self.bridges[bid].best_bpdu.external_rpc}\n" + \
                  f"I: {self.bridges[bid].best_bpdu.internal_rpc}"
                  for bid in positions.keys()}
        nx.draw_networkx_labels(G, positions, labels=labels)
        _, colors_edges = zip(*nx.get_edge_attributes(G,'color').items())

        color_set = ['orange', 'yellow', 'green', 'red', 'pink']
        for bid, bridge in self.bridges.items():
            G.nodes[bid]['color'] =  color_set[bridge.region_name]

        _, colors_nodes = zip(*nx.get_node_attributes(G,'color').items())

        return G, positions, edge_labels, colors_edges, colors_nodes

    def save(self, name):
        with open(name, 'wb') as handle:
            pickle.dump((self.bridges, self.edges), handle, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, name):
        with open(name, 'rb') as handle:
            self.bridges, self.edges = pickle.load(handle)

    def __repr__(self):
        return ",".join(map(str, self.bridges.keys()))