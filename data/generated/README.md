# data/generated

Lưu dữ liệu thực nghiệm đã sinh cho từng tổ hợp topology × server distribution × difficulty × version. Nên dùng quy ước tên file thể hiện đủ bốn thành phần và lưu metadata đi kèm.

Mỗi dataset cần thể hiện tài nguyên server, tài nguyên link, VNF, request theo thời gian, nguồn/đích, bandwidth, chuỗi VNF và deadline.

## Các file nên tạo

Nên tạo các file dữ liệu, không tạo mã nguồn trong thư mục này:

- `manifest.csv` hoặc `manifest.json`: danh sách 108 dataset và metadata của từng dataset.
- `dataset_<topology>_<distribution>_<difficulty>_<version>.json`: dữ liệu của từng cấu hình.
- `vnf_catalog.json`: danh mục 10 loại VNF và nhu cầu tài nguyên/thời gian khởi tạo.
- `README.md`: quy ước đặt tên và schema dataset.
