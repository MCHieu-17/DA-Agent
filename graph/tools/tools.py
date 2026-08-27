"""
tools.py
Chia 2 nhóm tool:
  1. Data tools  - đọc metadata/schema/sample/SQL, KHÔNG thực thi code tùy ý.
  2. Execution tools - chạy code Python do LLM sinh ra, luôn trong sandbox cách ly
     (ví dụ E2B Code Interpreter hoặc Daytona). Đây là nhóm rủi ro cao nhất
     nên phải cách ly khỏi process chính.
"""

import pandas as pd
from langchain_core.tools import tool

# ============================================================= #
#                    NHÓM 1: DATA TOOLS (an toàn)                #
# ============================================================= #

# Trong thực tế nên load qua một Data Registry / DB thay vì dict tạm.
_DATASET_REGISTRY: dict[str, pd.DataFrame] = {}


def register_dataset(dataset_id: str, df: pd.DataFrame) -> None:
    _DATASET_REGISTRY[dataset_id] = df


@tool
def get_schema(dataset_id: str) -> dict:
    """Trả về tên cột, dtype, số dòng, số giá trị null của dataset.
    Dùng ở node profile_data để planner hiểu cấu trúc dữ liệu trước khi lập plan.
    """
    df = _DATASET_REGISTRY.get(dataset_id)
    if df is None:
        return {"error": f"dataset_id '{dataset_id}' không tồn tại"}
    return {
        "n_rows": len(df),
        "columns": [
            {
                "name": col,
                "dtype": str(df[col].dtype),
                "n_null": int(df[col].isnull().sum()),
            }
            for col in df.columns
        ],
    }


@tool
def get_sample_rows(dataset_id: str, n: int = 5) -> str:
    """Lấy n dòng mẫu đầu tiên của dataset để LLM hiểu format dữ liệu thực tế."""
    df = _DATASET_REGISTRY.get(dataset_id)
    if df is None:
        return f"dataset_id '{dataset_id}' không tồn tại"
    return df.head(n).to_markdown(index=False)


@tool
def sql_query(dataset_id: str, query: str) -> str:
    """Chạy SQL read-only trực tiếp trên dataset khi câu hỏi đơn giản
    (không cần sinh code Python phức tạp). Dùng pandasql/duckdb phía dưới.
    """
    import duckdb

    df = _DATASET_REGISTRY.get(dataset_id)
    if df is None:
        return f"dataset_id '{dataset_id}' không tồn tại"
    try:
        con = duckdb.connect()
        con.register("df", df)
        result = con.execute(query).df()
        return result.to_markdown(index=False)
    except Exception as e:  # noqa: BLE001
        return f"SQL error: {e}"


# ============================================================= #
#              NHÓM 2: EXECUTION TOOLS (chạy sandbox)            #
# ============================================================= #

@tool
def run_python_sandbox(code: str, dataset_id: str) -> dict:
    """Thực thi code Python trong sandbox cách ly (E2B/Daytona).
    Trả về stdout, stderr, status và danh sách artifact (chart/csv) sinh ra.
    KHÔNG chạy code trực tiếp trong process chính vì code do LLM sinh ra
    có thể đọc/ghi/xoá file hệ thống hoặc treo tài nguyên.
    """
    # --- Ví dụ tích hợp thật với E2B (cần cài `e2b-code-interpreter` + API key) ---
    # from e2b_code_interpreter import Sandbox
    # with Sandbox() as sbx:
    #     df = _DATASET_REGISTRY.get(dataset_id)
    #     if df is not None:
    #         sbx.files.write("/home/user/data.csv", df.to_csv(index=False))
    #     execution = sbx.run_code(code)
    #     artifacts = [f"artifact_{i}" for i, r in enumerate(execution.results) if r.png]
    #     return {
    #         "status": "error" if execution.error else "success",
    #         "stdout": "\n".join(execution.logs.stdout),
    #         "stderr": "\n".join(execution.logs.stderr) if execution.error else "",
    #         "traceback": str(execution.error) if execution.error else "",
    #         "artifacts": artifacts,
    #     }

    # --- Bản stub để demo local (THAY bằng sandbox thật khi lên production) ---
    import io
    import contextlib
    import traceback as tb

    df = _DATASET_REGISTRY.get(dataset_id)
    local_vars = {"df": df, "pd": pd}
    stdout_buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buf):
            exec(code, {}, local_vars)  # noqa: S102 - demo only, PHẢI thay bằng sandbox thật
        return {
            "status": "success",
            "stdout": stdout_buf.getvalue(),
            "stderr": "",
            "traceback": "",
            "artifacts": [],
        }
    except Exception:
        return {
            "status": "error",
            "stdout": stdout_buf.getvalue(),
            "stderr": tb.format_exc(),
            "traceback": tb.format_exc(),
            "artifacts": [],
        }


@tool
def save_artifact(sandbox_path: str) -> str:
    """Copy file (chart, report) từ sandbox ra storage ngoài (S3/local)
    để đính kèm vào câu trả lời cuối cho user.
    """
    # TODO: implement copy từ sandbox filesystem ra storage thật
    return f"saved:{sandbox_path}"


@tool
def web_search(query: str) -> str:
    """Tra cứu thông tin/định nghĩa domain bên ngoài khi câu hỏi cần kiến thức
    nằm ngoài dataset (ví dụ định nghĩa một chỉ số tài chính)."""
    # TODO: nối với search provider thật (Tavily/SerpAPI/...)
    return f"[stub] kết quả tra cứu cho: {query}"


DATA_TOOLS = [get_schema, get_sample_rows, sql_query]
EXECUTION_TOOLS = [run_python_sandbox, save_artifact]
AUX_TOOLS = [web_search]
