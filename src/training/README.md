# src/training

Quản lý vòng lặp training, episode, batch replay, cập nhật target model, checkpoint và seed. Các giá trị tham khảo trong tài liệu: 100 episodes, batch size 32, replay size 10000, gamma 0.95, learning rate 0.001, epsilon từ 1.0 đến tối thiểu 0.01, cập nhật target mỗi 10 episodes.

## Các file nên tạo

- `trainer.py`: vòng lặp train theo episode và time slot.
- `episode.py`: logic chạy một episode.
- `reproducibility.py`: seed, log phiên bản và thiết lập tái lập.
- `checkpoint_manager.py`: quản lý checkpoint/best model.
- `logger.py`: ghi reward, loss, acceptance rate và cost theo episode.
