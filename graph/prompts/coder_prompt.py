from langchain_core.prompts import ChatPromptTemplate


SYSTEM_HEADLESS = """
MÔI TRƯỜNG HEADLESS (không có GUI).
Nếu vẽ biểu đồ:
- TUYỆT ĐỐI KHÔNG dùng plt.show() hay fig.show().
- Hãy lưu file vào thư mục '{artifacts_dir}'.
- Ví dụ:
  plt.savefig('{artifacts_dir}/chart.png')
  fig.write_html('{artifacts_dir}/chart.html')
- Sau đó print ra đường dẫn file đã lưu.
"""

SYSTEM_NORMAL = (
    "Bạn là chuyên gia Data Engineer. Viết mã Python.\n\n" + SYSTEM_HEADLESS
)


HUMAN_NORMAL = """
- Các file CSV được phép sử dụng (dùng đúng đường dẫn tuyệt đối này):
{data_files}

- Dữ liệu schema:
{schema_str}

- Lịch sử các bước trước:
{past_steps}

- Bước hiện tại cần làm:
{current_step}

Hãy viết mã Python.
Chỉ được import các module trong allowlist: {allowed_imports}.

Mỗi bước chạy trong một process độc lập: không dùng biến từ bước trước,
hãy đọc lại CSV khi cần. Luôn print kết quả dữ liệu cần dùng để trả lời user.
Không tự ý tạo lại thư mục '{artifacts_dir}'.
"""


SYSTEM_ERROR = (
    "Bạn là chuyên gia Data Engineer. Nhiệm vụ của bạn là SỬA LỖI mã Python.\n\n"
    + SYSTEM_HEADLESS
)


HUMAN_ERROR = """
- Các file CSV được phép sử dụng (dùng đúng đường dẫn tuyệt đối này):
{data_files}

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

- Phân tích và hướng sửa từ debugger:
{debug_feedback}

Hãy viết lại mã Python để khắc phục lỗi.
Chỉ được import các module trong allowlist: {allowed_imports}.
Mỗi lần chạy là một process độc lập; hãy đọc lại CSV khi cần.
Luôn print kết quả dữ liệu cần dùng để trả lời user ra stdout.
"""


normal_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_NORMAL),
    ("human", HUMAN_NORMAL),
])

error_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_ERROR),
    ("human", HUMAN_ERROR),
])
