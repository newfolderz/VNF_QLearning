# src/evaluation

Đánh giá agent RL và baseline trên cùng dataset/test split. Tính acceptance rate và cost; lưu thêm các thống kê cần thiết để kiểm tra vi phạm tài nguyên, latency/deadline, thời gian chạy và độ ổn định giữa các seed.

## Các file nên tạo

- `evaluator.py`: chạy một thuật toán trên test split.
- `metrics.py`: tính acceptance rate, cost, reward và các violation.
- `compare.py`: so sánh RL với Random/GMinC/GMaxR.
- `aggregate.py`: tổng hợp kết quả theo topology, difficulty và distribution.
- `export.py`: xuất metrics sang `results/metrics/`.
