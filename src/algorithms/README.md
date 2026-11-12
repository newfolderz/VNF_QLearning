# src/algorithms

Triển khai các thuật toán đối chứng để chương 4 so sánh công bằng với RL:

- Random: chọn ngẫu nhiên node đủ tài nguyên.
- GMinC: ưu tiên lựa chọn có chi phí thấp nhất.
- GMaxR: ưu tiên node còn nhiều tài nguyên nhất.

Các thuật toán cần dùng chung interface với agent RL và cùng điều kiện khả thi.

## Các file nên tạo

- `base.py`: interface chung cho mọi thuật toán placement/routing.
- `random_baseline.py`: baseline Random.
- `greedy_min_cost.py`: baseline GMinC.
- `greedy_max_resources.py`: baseline GMaxR.
- `heuristics.py`: hàm dùng chung để lọc node/route khả thi, nếu cần.
