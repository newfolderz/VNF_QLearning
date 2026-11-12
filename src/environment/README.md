# src/environment

Xây dựng môi trường mô phỏng động theo time slot. Cần mô tả rõ state, action, transition, điều kiện kết thúc, cập nhật tài nguyên và xử lý request bị từ chối.

State tối thiểu theo tài liệu gồm tài nguyên còn lại của node/link, VNF đã đặt và request mới/đang chờ. Action gồm chọn server đặt VNF và chọn route khả thi.

## Các file nên tạo

- `network_env.py`: môi trường chính, reset/step và vòng đời time slot.
- `state.py`: xây dựng và chuẩn hóa state đưa vào agent.
- `action.py`: không gian action, chọn node và route.
- `transition.py`: cập nhật placement, route, tài nguyên và request.
- `reward.py`: reward theo cost và acceptance rate với hệ số rho.
- `constraints.py`: kiểm tra CPU, RAM, memory, bandwidth, latency và deadline.
- `routing.py`: tìm route khả thi/shortest path theo yêu cầu chương 3.
