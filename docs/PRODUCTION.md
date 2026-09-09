# Production trên Linux

API chỉ dùng trong nội bộ qua reverse proxy TLS. Không public `langgraph dev`.
Worker là thành phần tin cậy có quyền Docker/mount; API chạy bằng user riêng,
không có Docker socket hay credentials PostgreSQL nguồn. Code LLM chạy trong
container gVisor mới cho mỗi attempt; validator chạy trong container mới, input readonly.

## Cài đặt

1. Chuẩn bị Linux với Docker, gVisor `runsc`, `e2fsprogs`, `util-linux`, Python 3.12.
   Cài runsc theo https://gvisor.dev/docs/user_guide/install/ và đăng ký Docker runtime
   theo https://gvisor.dev/docs/user_guide/quick_start/docker/ .
2. Cài `requirements.txt` trong `/srv/da-agent/.venv`. Build image:
   `docker build -f deploy/Dockerfile.sandbox -t REGISTRY/da-sandbox:VERSION .`
   Push vào registry riêng, lấy RepoDigest và đặt
   `DA_SANDBOX_IMAGE=REGISTRY/da-sandbox@sha256:...`.
   Không dùng tag động cho worker. Base image và digest phát hành phải được kiểm tra,
   quét lỗ hổng và cập nhật theo quy trình vận hành của tổ chức.
3. Tạo PostgreSQL vận hành riêng; đặt `DA_QUEUE_DSN` và chạy
   `python -m scripts.init_queue`. Tài khoản runtime chỉ cần SELECT/INSERT/UPDATE
   trên `da_jobs`; tài khoản migration riêng mới cần CREATE.
4. Copy hai registry example thành file cấu hình ngoài repo. Đặt
   `DA_SOURCE_REGISTRY`, `DA_AUTH_REGISTRY`. Chỉ cấp cột được phép gửi tới LLM;
   cột nhạy cảm bị loại trước khi lập snapshot, code cũng không nhìn thấy chúng.
   Token người dùng phải ngẫu nhiên >=32 bytes, chỉ lưu SHA256. Không lưu token rõ.
5. Environment cho API: `DA_ENVIRONMENT=production`, `DA_EXECUTOR_BACKEND=gvisor`,
   `DA_QUEUE_DSN`, hai đường dẫn registry. Environment cho worker thêm model key,
   `DA_SANDBOX_IMAGE`, `DA_REPORTING_DSN` theo registry và `DA_SNAPSHOT_DIR`.
   Worker cần gọi `load_dotenv` trước import configuration nếu dùng `.env`;
   systemd EnvironmentFile là cách cấu hình production.
6. Dùng unit files mẫu trong deploy. Khởi động một worker trước; tối đa 5 instance
   sau khi benchmark RAM/disk. API account chỉ có quyền đọc artifact và registry,
   không được sửa code, registry, snapshots hoặc outputs.

## Quyền PostgreSQL nguồn

Tạo role LOGIN riêng, không superuser, không BYPASSRLS, không owner và không có
role ghi. Chỉ GRANT USAGE schema + SELECT trên reporting views được duyệt.
Không dùng tài khoản ứng dụng quản trị. Broker đặt search_path=pg_catalog,
transaction REPEATABLE READ READ ONLY, statement timeout 300s và lock timeout 5s.
AST gate chỉ nhận SELECT trên logical dataset IDs và hàm được phép; mỗi truy vấn
có savepoint để debug không phá snapshot của lượt. View/hàm trong reporting schema
do quản trị viên kiểm tra, không nhận từ payload người dùng.

## Quota và lifecycle

Mỗi sandbox: 2 CPU, RAM 4 GiB, 128 PID, rootfs readonly, network none, tmpfs /tmp
128 MiB. Vùng spill/output dùng filesystem ext4 riêng, tối đa 20 GiB trên ổ đĩa,
không dùng tmpfs cho dữ liệu lớn. Worker cần loop devices và mount privilege.
Provision tối thiểu 40 GiB trống mỗi attempt đang chạy để seal/copy outputs;
benchmark I/O của bước copy này trước khi tăng concurrency.

Mỗi job có lease 30s, heartbeat 5s, deadline 15 phút. Kết quả được ghi bằng lease
token; job mất worker bị đánh dấu failed, không tự thực thi lại trên snapshot mới.
Parent dừng process tree và dọn container/volume khi hủy hoặc hết giờ.
Chạy janitor định kỳ để xử lý worker/host bị tắt đột ngột. Giữ artifact 7 ngày;
thực hiện backup metadata theo chính sách tổ chức. Không xóa snapshot đang được job dùng.

## API

`Authorization: Bearer TOKEN`

POST `/runs`:
```json
{"messages":[{"content":"Tính tổng Sales theo City"}],"source_refs":["sales"]}
```

Trả 202 với id. GET `/runs/{id}` để đọc trạng thái/kết quả; DELETE cùng URL để hủy.
Follow-up gửi previous_job_id; lịch sử được lấy từ kết quả phía server.
File tải qua `/runs/{id}/artifacts/{artifact_id}`, kiểm tra quyền sở hữu mỗi lần.
HTML luôn attachment với CSP sandbox và nosniff; frontend không nhúng HTML vào cùng origin.

## Gate phát hành

Chạy unit tests, PostgreSQL integration và `DA_TEST_GVISOR=1` trên Linux thật.
Kiểm tra secret/network isolation, symlink, output/PID/RAM/disk limits, process con,
timeout/hủy, worker crash, permission khác người dùng. Không coi test Docker command
builder là chứng nhận isolation. Nếu thiếu runtime/image pinned, worker không khởi động.
Đo cold/warm cache, 100 MB/1 GB/10 GB, 1/5 job đồng thời; chưa có SLA 10 GB khi
chưa chạy trên phần cứng đích. Metrics ghi vào mỗi kết quả, gồm provider/model,
thời gian node/call và usage; usage thiếu được ghi null, charge dùng ước lượng bảo thủ.
