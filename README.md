# DA-Agent local

DA-Agent là một graph LangGraph chạy local để phân tích file CSV bằng Python/pandas.
Luồng được giữ gọn: Intake → Chat/Clarify/Data Profiling → Planner → Coder →
Execute → Debug/Replan → Synthetic → Verification → Finalize.

## Cài đặt và chạy

~~~bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env
langgraph dev
~~~

Điền một trong `GEMINI_API_KEY` hoặc `DEEPSEEK_API_KEY` vào `.env`, rồi chọn
provider/model nếu cần:

~~~dotenv
DA_LLM_PROVIDER=gemini
DA_LLM_MODEL=gemini-3.5-flash-lite
DA_LLM_REQUEST_TIMEOUT_SECONDS=30
DA_LLM_MAX_RETRIES=2
DA_EXECUTION_TIMEOUT_SECONDS=60
~~~

Entrypoint Studio là `main.py:app`. Payload mẫu:

~~~json
{
  "messages": [{"type": "human", "content": "Tính tổng Sales theo City và vẽ biểu đồ cột."}],
  "file_paths": ["datasets/SuperMarket Analysis.csv"]
}
~~~

Chỉ file `.csv` local được hỗ trợ; đường dẫn tương đối được tính từ thư mục dự án.
Chat không cần file. CSV nguồn được nạp dưới dạng chuỗi để không làm mất số 0 đầu
hoặc tự suy diễn ngày. Profile gồm thống kê toàn file, reservoir sample và nhận diện
định dạng ngày; profile chỉ được dùng lại trong cùng thread khi path, size và mtime
không đổi.

## Runtime và kết quả

Mỗi bước chạy bằng chính `sys.executable` trong một subprocess. Code sinh ra có bốn
helper: `load_input`, `save_table`, `save_scalar`, `save_chart`, cùng biến
`ARTIFACTS_DIR`. Bảng giữa các bước được lưu Parquet. Mỗi bước phải gọi đúng một
hàm `save_*`; executor kiểm tra loại, cột, row count, non-null và uniqueness theo
kế hoạch trước khi chuyển kết quả tới Verification.

~~~text
artifacts/<run_id>/plan_<version>/step_<number>/attempt_<number>/
    context.json
    code.py
    stdout.log
    stderr.log
    result.json
    result.parquet       # với kết quả bảng
    chart.png            # ví dụ artifact công khai
~~~

Output chính gồm `final_answer`, `workflow_status`, `artifacts`, `step_results`,
`attempt_history` và `plan_history`.

> Cảnh báo: đây không phải sandbox. Code do LLM sinh có toàn quyền của tài khoản
> đang chạy ứng dụng: có thể đọc/ghi file, dùng mạng, đọc biến môi trường và chạy
> lệnh hệ thống. Chỉ chạy trên máy và dữ liệu mà bạn tin cậy.

Chạy smoke test bằng `pytest -q`.
