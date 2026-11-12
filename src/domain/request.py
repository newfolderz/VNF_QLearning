from .network import Network


class Request:
    def __init__(
        self,
        idx,
        arrival_time,
        start,
        dest,
        Fr: list,
        bandwidth,
        delay,
        start_time=None,
    ):
        self.idx = idx

        # time
        self.arrival = arrival_time
        self.start_time = arrival_time if start_time is None else start_time

        # params
        self.st = start
        self.d = dest
        self.Fr = Fr
        self.br = bandwidth
        self.dr = delay


class SFC:
    def __init__(self, request: Request, start=None):
        self.request = request
        if start is None:
            start = self.request.arrival
        self.start = start
        self.route_nodes = []
        self.F_nodes = []

    def to_dict(self):
        return {
            'start': self.start,
            'route': self.route_nodes,
            'servers': self.F_nodes
        }

    @classmethod
    def from_dict(cls, request: Request, info: dict):
        SFC = cls(request)
        SFC.start = info['start']
        SFC.route_nodes = info['route']
        SFC.F_nodes = info['servers']
        return SFC


def requests_to_file(requests, path):
    with open(path, 'w') as f:
        f.write(str(len(requests)) + '\n')
        for req in requests:
            f.write(' '.join([str(info) for info in [req.arrival, req.lifetime,
                                                     req.bw, req.mem, req.cpu, req.ingress, req.egress]]))
            f.write(' ' + ','.join([str(vnf) for vnf in req.VNFs]) + '\n')


def file_to_requests(path):
    with open(path) as f:
        R = int(f.readline())
        requests = []
        for idx in range(R):
            line = f.readline().split()
            arrival_time = float(line[0])
            lifetime = float(line[1])
            bandwidth = float(line[2])
            memory = float(line[3])
            cpu = float(line[4])
            ingress = line[5]
            egress = line[6]
            VNFs = [int(vnf) for vnf in line[7].split(',')]
            req = Request(idx, arrival_time, lifetime, ingress, egress, VNFs, bandwidth, memory, cpu)
            requests.append(req)

        return requests
