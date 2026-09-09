# Validation — 2026-09-08

Môi trường: Windows, Python trong Conda `da_agent`, PostgreSQL 18 trong container
test tạm thời; image Linux Python 3.12 build từ Dockerfile.sandbox.

## Kết quả đã quan sát

- Lượt cuối: **103 passed, 8 skipped** trong 111,24 giây. Tám ca bị skip
  là các probe gVisor cần Linux/runsc; PostgreSQL thật và image smoke đã chạy.
- Bộ kiểm thử bao gồm flow/recovery, source ACL, snapshot, SQL gate, provider budgets,
  telemetry, API authorization, PostgreSQL snapshot/savepoint/queue lease và image smoke test.
- Ba ca live bằng Gemini: tổng Sales, Sales theo tháng, missing count theo từng cột:
  đều PASS với oracle đối chiếu cột/hàng, không chỉ tìm số trong output.
- Báo cáo live bản cuối `artifacts/live_evaluations/20260908T075935791374.json`:
  p50 13,52 giây; thời gian lớn nhất trong 3 ca 13,81 giây;
  median input tokens cộng toàn lượt 7.424. Ba mẫu chưa đủ để suy ra SLA p95.
  Lượt trước phát hiện planner nhầm tên cột nguồn với cột assertion đầu ra;
  đã sửa mô tả schema, prompt và thông báo replan, thêm regression test rồi chạy lại.
- Benchmark storage/execution: CSV 104.857.610 bytes, 11.650.844 dòng,
  tạo snapshot 30,08 giây; năm truy vấn tổng hợp đồng thời đều đúng,
  thời gian thực thi chung 3,07 giây. Chạy backend local, dữ liệu tổng hợp lặp lại;
  không bao gồm profiling, LLM hay overhead gVisor.
  Báo cáo: `artifacts/benchmarks/95009b8f9e7a4453808b64d2c6991e00/report.json`.
- Image sandbox build thành công; Python runtime và validator chạy được trong
  container Linux không network, rootfs readonly với fixture code tin cậy.

## Gate còn cần môi trường đích

Docker Desktop hiện không có runtime runsc. Các test thực sự kiểm tra gVisor
được đánh dấu riêng và **không được tính là pass** khi bị skip. Workflow CI Linux
cài runsc kèm sidecar binaries theo gói chính thức rồi chạy các probe này.
Chưa triển khai lên server production, chưa benchmark 1/10 GB hoặc tải production.

Không có báo cáo token/thời gian của phiên bản cũ, nên chưa kết luận phần trăm
giảm chi phí hoặc tốc độ trước/sau. Dùng scripts/benchmark.py với --baseline khi
có hai bộ report cùng model/dataset/cấu hình. Usage thiếu được ghi null thay vì 0.

## Tái lập

```powershell
$env:DA_EXECUTOR_BACKEND = 'local'
# Chỉ trỏ vào database test tách biệt, không dùng database thật:
$env:DA_TEST_POSTGRES_DSN = 'postgresql://TEST_USER:TEST_PASSWORD@localhost/TEST_DB'
$env:DA_TEST_SANDBOX_IMAGE = 'da-agent-sandbox:implementation'
python -m pytest -q -p no:cacheprovider
python scripts/evaluate_live.py --repeat 3
python scripts/benchmark_data.py --size-mb 100 --concurrency 5
```

Nếu thư mục temp pytest cũ trên Windows bị ACL chặn, dùng --basetemp trỏ tới một
thư mục test mới dưới artifacts/. Không xóa hay thay ACL thư mục temp của người dùng.
