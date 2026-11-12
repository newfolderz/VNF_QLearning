import networkx as nx

class Network:
    def __init__(self, max_horizon=30):
        self.G = nx.Graph()
        # Khai báo tầm nhìn xa tối đa (VD: 30 time-slots)
        self.max_horizon = max_horizon 

    def add_server_node(self, name, cpu: float, ram: float, hdd: float,
                        cpu_cost: float, ram_cost: float, hdd_cost: float,
                        delay: float):
        self.G.add_node(name, id=self.G.number_of_nodes(), server=True,
                        c_cap=cpu, r_cap=ram, h_cap=hdd,
                        # Đổi thành mảng time-series
                        c_use=[0.0] * self.max_horizon, 
                        r_use=[0.0] * self.max_horizon, 
                        h_use=[0.0] * self.max_horizon,
                        c_cost=cpu_cost, r_cost=ram_cost, h_cost=hdd_cost,
                        d=delay)

    def add_switch_node(self, name):
        self.G.add_node(name, id=self.G.number_of_nodes(), server=False)

    def add_link(self, u, v, bandwidth: float, delay: float):
        self.G.add_edge(u, v,
                        b_cap=bandwidth, 
                        b_use=[0.0] * self.max_horizon, # Đổi thành mảng time-series
                        dl=delay)

    @property
    def server_nodes(self):
        return [node for node in self.G.nodes if self.G.nodes[node]['server']]

    @property
    def switch_nodes(self):
        return [node for node in self.G.nodes if not self.G.nodes[node]['server']]

    # ... (Các hàm c_max, r_max, h_max, b_max giữ nguyên) ...

    # Thêm tham số t (thời điểm trong tương lai, 0 là hiện tại)
    def remaining_cpu(self, node, t1=0, t2=None):
        if t2 is None:
            t2 = t1+1
        # Lấy max tài nguyên ĐÃ DÙNG trong khoảng [t1, t2)
        # Bọc max/min để tránh lỗi vượt quá max_horizon
        max_used = max(self.G.nodes[node]['c_use'][t1:t2])
        
        # Sức chứa trừ đi max_used sẽ ra Min Remaining
        return self.G.nodes[node]['c_cap'] - max_used

    def remaining_ram(self, node, t1=0, t2=None):
        if t2 is None:
            t2 = t1+1
        max_used = max(self.G.nodes[node]['r_use'][t1:t2])
        return self.G.nodes[node]['r_cap'] - max_used

    def remaining_hdd(self, node, t1=0, t2=None):
        if t2 is None:
            t2 = t1+1
        max_used = max(self.G.nodes[node]['h_use'][t1:t2])
        return self.G.nodes[node]['h_cap'] - max_used

    def remaining_bandwidth(self, u, v, t1=0, t2=None):
        if t2 is None:
            t2 = t1 +1
        max_used = max(self.G[u][v]['b_use'][t1:t2])
        return self.G[u][v]['b_cap'] - max_used
    # Hàm check mạng giờ phải check toàn bộ cửa sổ thời gian xem có lúc nào bị lố không
    def check_network_capacity(self):
        for node in self.server_nodes:
            if (max(self.G.nodes[node]['c_use']) > self.G.nodes[node]['c_cap'] or
                max(self.G.nodes[node]['r_use']) > self.G.nodes[node]['r_cap'] or
                max(self.G.nodes[node]['h_use']) > self.G.nodes[node]['h_cap']):
                return False

        for u, v in self.G.edges:
            if max(self.G[u][v]['b_use']) > self.G[u][v]['b_cap']:
                return False
        return True

    # --- HÀM MỚI: Tịnh tiến thời gian (Sliding Window) ---
    def advance_time(self):
        """
        Gọi hàm này mỗi khi manager.advance() nhích 1 time_slot.
        Nó sẽ vứt bỏ quá khứ (pop 0) và thêm slot tương lai (append 0.0)
        """
        for node in self.server_nodes:
            self.G.nodes[node]['c_use'].pop(0)
            self.G.nodes[node]['c_use'].append(0.0)
            self.G.nodes[node]['r_use'].pop(0)
            self.G.nodes[node]['r_use'].append(0.0)
            self.G.nodes[node]['h_use'].pop(0)
            self.G.nodes[node]['h_use'].append(0.0)
            
        for u, v in self.G.edges:
            self.G[u][v]['b_use'].pop(0)
            self.G[u][v]['b_use'].append(0.0)