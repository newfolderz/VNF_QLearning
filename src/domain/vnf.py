class VNF:
    def __init__(self, cpu: float, ram: float, hdd: float, delay: dict):
        self.cf = cpu
        self.rf = ram
        self.hf = hdd
        self.df = delay
