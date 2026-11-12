# src/agents

Triển khai tác tử học tăng cường, DQN, replay memory, target network và chính sách epsilon-greedy/epsilon-decay. Xác định rõ kích thước input `MDCnodes × 3 + 3`, hidden layer 128 và output `MDCnodes` theo mô hình trong chương 3, đồng thời cho phép cấu hình nếu cần mở rộng.

## Các file nên tạo

- `dqn.py`: kiến trúc mạng Q và forward pass.
- `replay_memory.py`: lưu và lấy mẫu experience.
- `agent.py`: chọn action, lưu experience và thực hiện replay/update.
- `policy.py`: epsilon-greedy và epsilon decay.
- `target_network.py`: cơ chế cập nhật target network nếu tách riêng.
- `checkpoint.py`: lưu/tải model và trạng thái huấn luyện.
