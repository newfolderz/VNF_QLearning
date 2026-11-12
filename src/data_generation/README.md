# Sinh dữ liệu thực nghiệm

Thư mục này chứa chương trình sinh dữ liệu cho bài toán VNF Placement & Routing. Entry point là [test_gen.py](./test_gen.py). Chương trình đọc topology từ [data/topologies/](../../data/topologies/) và ghi dataset JSON vào [data/generated/](../../data/generated/).

## 1. Kết quả sinh dữ liệu

Mỗi lần chạy tạo hoặc kiểm tra đủ:

| Loại | Số lượng | Vị trí | Mô tả |
|---|---:|---|---|
| Dataset JSON | 108 | `data/generated/dataset_*.json` | Dữ liệu cho từng cấu hình thực nghiệm |
| Manifest | 1 | `data/generated/manifest.json` | Danh sách và metadata của 108 dataset |
| VNF catalog | 1 | `data/generated/vnf_catalog.json` | Danh mục 10 loại VNF |

Số lượng 108 được tính như sau:

```text
3 topology × 4 server distribution × 3 difficulty × 3 version = 108
```

## 2. Các chiều dữ liệu

### Topology

| Giá trị | File node | File edge | Ý nghĩa |
|---|---|---|---|
| `nsf` | `nsf_nodes.csv` | `nsf_edges.txt` | Mạng NSF |
| `conus` | `conus_nodes.csv` | `conus_edges.txt` | Mạng CONUS |
| `cogent` | `cogent_nodes.csv` | `cogent_edges.txt` | Mạng COGENT |

File node gồm tọa độ `X`, `Y`; file edge gồm node nguồn, node đích và thông tin bổ sung. Khoảng cách Euclid giữa hai node được dùng để tính delay của link.

### Server distribution

| Giá trị | Cách chọn server |
|---|---|
| `uniform` | Chọn ngẫu nhiên khoảng 30% số node |
| `urban` | Chọn khoảng 30% node có bậc kết nối cao nhất |
| `rural` | Chọn khoảng 30% node có bậc kết nối thấp nhất |
| `centers` | Chọn khoảng 10% node có bậc kết nối cao nhất |

Các node không được chọn làm server sẽ có kiểu `switch`.

### Difficulty

| Giá trị | CPU/RAM/HDD demand | Bandwidth request | Số VNF tối đa trong chain |
|---|---:|---:|---:|
| `easy` | 1–3 | 0–10 | 2 |
| `normal` | 2–6 | 1–15 | 3 |
| `hard` | 5–12 | 1–20 | 4 |

### Version

| Giá trị | Mục đích |
|---:|---|
| `1` | Phiên bản random seed thứ nhất |
| `2` | Phiên bản random seed thứ hai |
| `3` | Phiên bản random seed thứ ba |

Version không thay đổi topology hay difficulty; nó tạo một mẫu dữ liệu ngẫu nhiên độc lập cho cùng một cấu hình.

## 3. Quy ước tên file

```text
dataset_<topology>_<distribution>_<difficulty>_v<version>.json
```

Ví dụ:

```text
dataset_conus_centers_normal_v2.json
```

Trong đó:

| Thành phần | Giá trị hợp lệ |
|---|---|
| `<topology>` | `nsf`, `conus`, `cogent` |
| `<distribution>` | `uniform`, `rural`, `urban`, `centers` |
| `<difficulty>` | `easy`, `normal`, `hard` |
| `<version>` | `1`, `2`, `3` |

## 4. Cấu trúc một dataset JSON

Mỗi dataset có cấu trúc cấp cao:

```json
{
  "schema_version": "1.0",
  "metadata": {},
  "network": {},
  "vnfs": [],
  "requests": []
}
```

### 4.1. `metadata`

| Trường | Kiểu | Mô tả |
|---|---|---|
| `topology` | string | Tên topology |
| `server_distribution` | string | Quy tắc phân bố server |
| `difficulty` | string | Mức độ khó |
| `version` | integer | Phiên bản dữ liệu, từ 1 đến 3 |
| `duration` | integer | Tổng thời gian mô phỏng, hiện là 50 slot |
| `train_slots` | integer | 10 slot đầu dành cho train |
| `test_slots` | integer | 40 slot sau dành cho test |

### 4.2. `network.nodes[]`

Node switch có dạng:

```json
{ "id": 0, "type": "switch" }
```

Node server có thêm tài nguyên và chi phí:

| Trường | Kiểu | Mô tả |
|---|---|---|
| `id` | integer | ID node |
| `type` | string | `server` hoặc `switch` |
| `cpu_capacity` | number | Sức chứa CPU |
| `ram_capacity` | number | Sức chứa RAM |
| `hdd_capacity` | number | Sức chứa HDD |
| `cpu_cost` | number | Chi phí sử dụng CPU |
| `ram_cost` | number | Chi phí sử dụng RAM |
| `hdd_cost` | number | Chi phí sử dụng HDD |
| `delay` | number | Delay xử lý tại server |

Các trường tài nguyên và chi phí chỉ xuất hiện với node có `type = "server"`.

### 4.3. `network.links[]`

| Trường | Kiểu | Mô tả |
|---|---|---|
| `source` | integer | Node đầu link |
| `target` | integer | Node cuối link |
| `distance` | number | Khoảng cách giữa hai node |
| `bandwidth_capacity` | number | Băng thông tối đa của link |
| `delay` | number | Delay truyền trên link |

`network.server_nodes` là mảng ID của tất cả server trong topology đó.

### 4.4. `vnfs[]`

Mỗi dataset có 10 VNF:

| Trường | Kiểu | Mô tả |
|---|---|---|
| `id` | integer | ID VNF, từ 0 đến 9 |
| `cpu_demand` | number | CPU cần dùng |
| `ram_demand` | number | RAM cần dùng |
| `hdd_demand` | number | HDD cần dùng |
| `processing_delay` | number | Delay xử lý VNF |

### 4.5. `requests[]`

Mỗi dataset hiện có 50 request:

| Trường | Kiểu | Mô tả |
|---|---|---|
| `id` | integer | ID request |
| `arrival_time` | integer | Thời điểm request đến |
| `start_time` | integer | Thời điểm bắt đầu xử lý |
| `source` | integer | Node nguồn |
| `destination` | integer | Node đích |
| `bandwidth` | number | Băng thông request yêu cầu |
| `deadline` | number | Hạn hoàn thành request |
| `vnf_chain` | integer[] | Chuỗi ID các VNF cần chạy |
| `placement_hint` | integer[] | Gợi ý server tương ứng với VNF chain |
| `route_hint` | integer[] | Đường đi ngắn nhất từ source đến destination |

`placement_hint` và `route_hint` là dữ liệu gợi ý ban đầu cho thực nghiệm; thuật toán placement/routing vẫn có thể tự tìm nghiệm khác.

## 5. Cách chạy

Chạy từ thư mục gốc project:

```powershell
e:/LABS/Q-learning/again/.venv/bin/python.exe src/data_generation/test_gen.py
```

Mặc định chương trình dùng seed `2026` và giữ nguyên các dataset đã tồn tại. Để sinh lại toàn bộ 108 dataset:

```powershell
e:/LABS/Q-learning/again/.venv/bin/python.exe src/data_generation/test_gen.py --force
```

Để dùng seed khác:

```powershell
e:/LABS/Q-learning/again/.venv/bin/python.exe src/data_generation/test_gen.py --seed 1234 --force
```

Sau khi chạy, kiểm tra nhanh:

```powershell
(Get-ChildItem data/generated -Filter 'dataset_*.json').Count
```

Kết quả mong đợi là `108`.

## 6. Tính tái lập và giới hạn

- Seed được tạo riêng cho từng tổ hợp `topology`, `distribution`, `difficulty`, `version`.
- Chạy lại cùng seed sẽ tạo cùng dữ liệu.
- Chương trình không xóa file cũ; dùng `--force` để ghi đè dataset.
- Dataset mô tả tài nguyên, request, route hint và placement hint; việc kiểm tra khả thi cuối cùng thuộc về environment hoặc thuật toán đánh giá.
