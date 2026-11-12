# src

Mã nguồn chính của hệ thống. Các module nên phụ thuộc theo hướng: `domain` → `environment` → `agents/algorithms` → `training/evaluation`.

## Các file nên tạo trong thư mục này

Không nên đặt toàn bộ mã vào một file lớn. Có thể tạo:

- `__init__.py`: đánh dấu package nếu bạn dùng package Python.
- `README.md`: mô tả ranh giới và quan hệ phụ thuộc giữa các module.
- `common/` nếu cần các tiện ích dùng chung; nếu tạo folder này, thêm README riêng.
