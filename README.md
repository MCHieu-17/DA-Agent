# Data Analysis Agent

Phiên bản state 2: intake trước profiling, snapshot CSV/Parquet, DuckDB SQL,
PostgreSQL broker chỉ đọc, giới hạn token có telemetry và executor gVisor.
Xem [thay đổi triển khai](docs/IMPLEMENTATION.md) và [hướng dẫn production](docs/PRODUCTION.md).
Production chỉ chạy trên Linux với runtime runsc và image được khóa bằng digest.
Local development phải bật rõ `DA_EXECUTOR_BACKEND=local`; đây không phải sandbox.

Agent profile CSV/Parquet, lập kế hoạch JSON, chạy DuckDB SQL/Python từng bước
và truy vấn PostgreSQL qua broker chỉ đọc.
Câu trả lời chỉ được công bố sau verification.

## Flow

Intake → chat / clarify / Data Profiling → analysis.

Nhánh analysis: Planner → Coder → Execute → Synthetic → Verification → Finalize.

- Execute thành công và còn bước: sang Coder của bước tiếp theo.
- Execute lỗi: Debug sửa bước hiện tại rồi Execute chạy lại.
- Hết debug: Planner lập lại toàn bộ kế hoạch nếu còn lượt replan.
- Verification yêu cầu sửa diễn đạt: quay lại Synthetic, dùng nguyên bằng chứng.
- Verification phát hiện thiếu/sai phân tích: replan; thiếu định nghĩa: Clarify.
- Hết ngân sách hoặc lỗi model: Finalize báo thất bại.
- Chat và Clarify trả lời trực tiếp. Route là conditional edge.

Đọc [graph/graph.py](graph/graph.py), [graph/state.py](graph/state.py) và
[configuration.py](configuration.py). Runtime trao đổi file nằm trong
[graph/runtime.py](graph/runtime.py). Import graph không tự vẽ ảnh.

## Chạy trên Windows

Kích hoạt môi trường dự án trước khi cài dependency; executor dùng chính interpreter này:

~~~powershell
conda activate da_agent
cd D:\KLTN\DA-Agent
python -c "import sys; print(sys.executable)"
python -m pip install -r requirements.txt
~~~

Chỉ tạo .env từ .env.example nếu chưa có. Điền GEMINI_API_KEY cho Gemini hoặc
DEEPSEEK_API_KEY cho DeepSeek. Provider self_host dùng Ollama.
Chọn provider/model qua configuration.py hoặc DA_LLM_PROVIDER, DA_LLM_MODEL;
các model mặc định được giữ nguyên.

~~~powershell
$env:PYTHONUTF8 = "1"
$env:DA_EXECUTOR_BACKEND = "local"
langgraph dev
~~~

Entrypoint vẫn là main.py:app. Chạy python main.py chỉ import graph.
Payload Studio:

~~~json
{
  "messages": [{"type": "human", "content": "Tính tổng Sales theo City và vẽ biểu đồ cột."}],
  "file_paths": ["datasets/SuperMarket Analysis.csv"]
}
~~~

Đường dẫn tương đối tính từ gốc dự án. Chat không cần CSV.
CSV không đọc được hoặc không có dữ liệu chuyển Clarify.

Gọi trực tiếp:

~~~python
from langchain_core.messages import HumanMessage
from main import app

state = app.invoke({
    "messages": [HumanMessage(content="Tính tổng Sales")],
    "file_paths": ["datasets/SuperMarket Analysis.csv"],
})
print(state["final_answer"])
state = app.invoke({
    **state,
    "messages": [*state["messages"], HumanMessage(content="Thế còn theo City?")],
})
~~~

Tạo thread mới cho checkpoint cũ: schema và kế hoạch dạng list chuỗi đã được thay
bằng profiling và kế hoạch có cấu trúc.

## Kế hoạch và kết quả từng bước

~~~json
{
  "steps": [{
    "step": 1,
    "goal": "Tính doanh thu theo tháng",
    "inputs": [{"source": "dataset_1", "columns": ["Date", "Sales"]}],
    "operation": "Đọc Date theo %m/%d/%Y, đổi Sales sang số, nhóm theo năm-tháng và tính tổng",
    "expected_output": {
      "type": "table",
      "columns": ["month", "revenue"],
      "description": "Một dòng mỗi tháng, sắp xếp tăng dần"
    }
  }],
  "success_criteria": ["Có doanh thu cho từng tháng"],
  "clarification_question": null
}
~~~

dataset_1 là CSV đầu vào thứ nhất. Bước sau có thể tham chiếu step_1.
Chỉ cho phép nguồn đã tồn tại, cột đã khai báo và bước trước trong cùng kế hoạch.
Mỗi bước có một đầu ra chính: table, scalar hoặc chart.

API dành cho code được sinh:

~~~python
from pathlib import Path
import pandas as pd
df = load_input("dataset_1")
df["month"] = pd.to_datetime(df["Date"], format="%m/%d/%Y").dt.strftime("%Y-%m")
df["Sales"] = pd.to_numeric(df["Sales"])
monthly = df.groupby("month", as_index=False)["Sales"].sum()
monthly = monthly.rename(columns={"Sales": "revenue"})
monthly.to_csv(Path(ARTIFACTS_DIR, "monthly.csv"), index=False)
save_table(monthly)
~~~

- load_input(source) chỉ nạp nguồn/cột khai báo trong bước.
- CSV được đọc dưới dạng chuỗi để giữ mã có số 0 đầu và ngày chưa rõ định dạng.
  Code phải chuyển số/ngày rõ ràng. Bảng trung gian Parquet giữ kiểu dữ liệu.
- Gọi đúng một trong save_table(df), save_scalar(value), save_chart(path).
- Helper tạo result.json; bảng chính lưu result.parquet.
- print() phục vụ log; chỉ stdout không đủ để hoàn thành bước.
- PNG/JPG/HTML/CSV trong thư mục lần chạy là public artifacts.
  JSON/Parquet là dữ liệu trung gian.
- Executor đọc lại manifest/file, kiểm tra loại kết quả và cột yêu cầu.
  Bảng rỗng có thể hợp lệ. Chỉ lần chạy thành công được truyền sang bước sau.

Cấu trúc thư mục:

~~~text
artifacts/<run_id>/plan_<version>/step_<number>/attempt_<debug_count>/
    context.json
    code.py
    stdout.log
    stderr.log
    result.json
    result.parquet
    monthly.csv
    monthly.png
~~~

step_results giữ kết quả thành công, preview, kiểu dữ liệu, đường dẫn, code và hash.
attempt_history ghi mọi lần chạy. plan_history giữ kế hoạch cũ và nguyên nhân replan.
Replan chạy lại từ bước 1; không tái sử dụng dữ liệu cũ.

Chế độ local vẫn cùng quyền hệ điều hành nên chỉ dùng cho phát triển;
environment được lọc và stdout/stderr có giới hạn. Chế độ gVisor chạy container
riêng với network tắt, input chỉ đọc và quota; không kế thừa secrets của agent.

## Data Profiling

Ưu tiên CSV đến khoảng 100 MB. Dùng pandas, không gọi LLM để tính profile.

| Phạm vi | Thống kê |
|---|---|
| Toàn file theo chunk | Số dòng/cột, null, độ dài chuỗi, khoảng trắng, mã có số 0 đầu, cột hằng |
| Giá trị chuyển thành số hữu hạn trên toàn file | Count, min/max, mean/std, zero/negative count, parse rate |
| Mẫu ngẫu nhiên xuyên suốt file | Distinct, top values, quartiles, IQR outliers, duplicate rows |
| Cột ứng viên ngày từ mẫu, kiểm tra format trên toàn file | Parse rate từng format, khoảng ngày, định dạng mơ hồ |

Mặc định: chunk 10.000 dòng, mẫu tối đa 5.000 dòng, seed 42, top 5.
Các trường scope và rows mô tả số liệu từ mẫu. Không suy diễn distinct/trùng
trong mẫu thành số chính xác trên toàn bảng. Ngày mơ hồ phải được làm rõ nếu ảnh hưởng phép tính.
Profiling không tự điền null, xóa trùng hay loại outlier.

profiles giữ JSON đầy đủ; profile_summary bỏ bớt trường tùy chọn để vừa prompt.
Nếu danh sách cột vẫn quá lớn, yêu cầu thu hẹp dữ liệu.
Nguồn file được hash SHA256 và tạo snapshot Parquet theo chunk. Profile cache
dùng snapshot bất biến và cấu hình profiling, tái sử dụng giữa các lượt. CSV_READ_OPTIONS
được dùng thống nhất khi profile và khi code nạp dữ liệu, gồm quy ước giá trị thiếu.

## Verification và giới hạn thử

Verification đọc câu hỏi/ngữ cảnh gốc, kế hoạch, code đã chạy, bằng chứng và bản nháp.
Quyết định gồm pass, revise_answer, replan, clarify.
Mỗi tiêu chí có trạng thái và evidence_refs dạng step_1.

Trước khi gọi model, kiểm tra kết quả còn tồn tại, đúng kế hoạch và chưa bị thay đổi.
Model đánh giá ý nghĩa câu trả lời; đây không phải chứng minh toán học.
Preview dài bị rút gọn không thay thế phép tính trên toàn bộ dữ liệu.
draft_answer không được ghi vào messages. Finalize chỉ công bố khi đạt;
khi thất bại, không công bố artifacts của phân tích chưa xác nhận.

| Cấu hình | Mặc định | Ý nghĩa |
|---|---:|---|
| PLAN_MAX_STEPS | 6 | Số bước tối đa mỗi kế hoạch |
| MAX_DEBUG_RETRIES_PER_STEP | 2 | Tối đa 3 lần chạy mỗi bước |
| MAX_REPLANS | 1 | Tối đa 2 kế hoạch mỗi câu hỏi |
| MAX_ANSWER_REVISIONS | 1 | Một lần viết lại bản nháp trong mỗi kế hoạch |
| EXECUTION_TIMEOUT_SECONDS | 60 | Timeout cho mỗi subprocess |

Các lỗi cần lập lại kế hoạch cùng dùng một ngân sách replan.
Lỗi dịch vụ LLM dùng retry transport có đo lường, rồi kết thúc; retry ẩn của provider bị tắt.
GRAPH_RECURSION_LIMIT tính từ các ngân sách trên. Thay cấu hình cần restart ứng dụng.
State chỉ ghi đè timeout/artifacts_dir khi bật ALLOW_STATE_CONFIG_OVERRIDES.

## Kiểm thử và sơ đồ

~~~powershell
python -m pytest -q
python scripts/draw_graph.py
python scripts/draw_graph.py --png
python scripts/evaluate_live.py --case total_sales
~~~

Test mặc định dùng LLM giả lập nhưng chạy graph, profiling và subprocess thật.
Sơ đồ mặc định xuất flow.mmd offline; --png gọi dịch vụ Mermaid để xuất flow.png.
Live evaluation dùng provider/key thật và ghi báo cáo vào artifacts/live_evaluations/.
Xem [scripts/live_cases.json](scripts/live_cases.json) và các kiểm thử trong tests/.
