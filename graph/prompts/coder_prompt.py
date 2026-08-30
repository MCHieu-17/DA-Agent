from langchain_core.prompts import ChatPromptTemplate


SYSTEM_NORMAL = """
Bạn là chuyên gia Data Engineer. Viết mã Python.

MÔI TRƯỜNG HEADLESS (không có GUI).
Nếu vẽ biểu đồ:
- TUYỆT ĐỐI KHÔNG dùng plt.show() hay fig.show().
- Hãy lưu file vào thư mục '{artifacts_dir}'.
- Ví dụ:
  plt.savefig('{artifacts_dir}/chart.png')
  fig.write_html('{artifacts_dir}/chart.html')
- Sau đó print ra đường dẫn file đã lưu.
"""


HUMAN_NORMAL = """
- Dữ liệu schema:
{schema_str}

- Lịch sử các bước trước:
{past_steps}

- Bước hiện tại cần làm:
{current_step}

Hãy viết mã Python.
Chỉ dùng các thư viện phổ biến cho phân tích dữ liệu
(pandas, numpy, matplotlib, plotly...).

Không tự ý tạo lại thư mục '{artifacts_dir}'.
"""


SYSTEM_ERROR = """
Bạn là chuyên gia Data Engineer.
Nhiệm vụ của bạn là SỬA LỖI mã Python.

MÔI TRƯỜNG HEADLESS (không có GUI).
Nếu vẽ biểu đồ:
- TUYỆT ĐỐI KHÔNG dùng plt.show() hay fig.show().
- Hãy lưu file vào thư mục '{artifacts_dir}'.
- Ví dụ:
  plt.savefig('{artifacts_dir}/chart.png')
  fig.write_html('{artifacts_dir}/chart.html')
- Sau đó print ra đường dẫn file đã lưu.
"""


HUMAN_ERROR = """
- Dữ liệu schema:
{schema_str}

- Lịch sử các bước trước:
{past_steps}

- Bước đang thực hiện:
{current_step}

- Mã đã chạy bị lỗi:
{code}

- Traceback / Error:
{traceback}

Hãy viết lại mã Python để khắc phục lỗi.
Lưu kết quả in ra vào stdout.
"""


normal_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_NORMAL),
    ("human", HUMAN_NORMAL),
])

error_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_ERROR),
    ("human", HUMAN_ERROR),
])