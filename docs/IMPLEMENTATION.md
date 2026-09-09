# Thay đổi phiên bản state 2

Giữ LangGraph và flow có verification độc lập. Intake chạy trước profiling;
chat/clarify có thể trả lời ngay trong lần gọi router. Analysis đi qua snapshot,
profile cache, planner, SQL/Python, execution, synthesis, verification và finalize.
Các lượt replan vẫn bắt đầu lại từ dữ liệu nguồn; không tái dùng kết quả lỗi.

Output budget đặt trên constructor provider trước structured output. Model clients
cache theo node. MeasuredModel lấy raw response để lưu usage, retry lỗi transport
có giới hạn; không retry parsing như lỗi mạng. Mỗi run giữ ledger riêng qua
ContextVar và mỗi node trả metrics vào state. Sync nodes chạy qua thread executor
khi dùng app.ainvoke; nhiều request không dùng chung state hay ledger.

Context coder/debugger chỉ có input trực tiếp; synthesis không nhận code/profile
không cần thiết; verification giữ code đầy đủ. Preview được rút theo hàng nguyên
vẹn; quá ngân sách với phần bằng chứng bắt buộc thì dừng, không cắt JSON.

SourceRef trỏ registry do quản trị viên cấp. Snapshot chỉ giữ cột được phép.
CSV đọc dạng string, chuyển Parquet theo chunk; PostgreSQL đi qua broker có
transaction snapshot. Input runtime bổ sung input_path và iter_input; engine SQL
đẩy group/filter/join xuống DuckDB. Kết quả được đọc bằng metadata và preview batch,
verification kiểm tra hash theo stream thay vì nạp lại cả bảng.

Local executor là công cụ phát triển, không phải sandbox dù environment đã được
lọc. Production yêu cầu gVisor: container không network, không secrets, input chỉ đọc,
CPU/RAM/PID/disk/log/timeout có giới hạn. Output được kiểm tra trong container mới.

API/hàng đợi ở service/, deployment mẫu ở deploy/, hướng dẫn ở PRODUCTION.md.
Không dùng checkpoint state cũ; tạo thread mới. Không có migration sửa dataset.
Operational PostgreSQL có migration tạo da_jobs, chạy riêng bằng scripts.init_queue.

## Kiểm tra

```powershell
conda activate da_agent
$env:DA_EXECUTOR_BACKEND = 'local'
python -m pytest -q -p no:cacheprovider
python scripts/evaluate_live.py --repeat 3
python scripts/benchmark.py artifacts/live_evaluations/REPORT.json
```

PostgreSQL integration chỉ dùng DB test tách biệt qua DA_TEST_POSTGRES_DSN.
Linux gVisor integration yêu cầu DA_TEST_GVISOR=1 và image pinned.
Không dùng model giả để đưa ra số liệu độ trễ inference hoặc phần trăm tiết kiệm token.
