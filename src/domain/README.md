# src/domain

Định nghĩa các đối tượng nghiệp vụ của chương 3: graph mạng `G=(V,E)`, server/VM, link, VNF, SFC/request, tài nguyên CPU/RAM/memory/bandwidth, latency, cost và trạng thái phân bổ.

Giữ các quy tắc miền độc lập với PyTorch và vòng lặp huấn luyện.

## Các file nên tạo

- `network.py`: graph, node/server, link và các thuộc tính tài nguyên.
- `vnf.py`: VNF, danh mục VNF và yêu cầu tài nguyên/thời gian khởi tạo.
- `request.py`: service request, SFC, source/destination, bandwidth và deadline.
- `allocation.py`: placement, route, segment và trạng thái phân bổ tài nguyên.
- `constants.py`: các enum/giá trị miền ổn định, nếu cần.
- `__init__.py`: export các kiểu miền công khai.
