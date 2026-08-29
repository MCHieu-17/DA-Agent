import os
import pandas as pd
from graph.state import DataAgentState


def _build_schema(csv_files: list) -> str:
    """Logic đọc CSV cũ của bạn, tách ra hàm riêng cho gọn."""
    schema_context = "Dưới đây là thông tin các bảng dữ liệu:\n\n"
    for file_path in csv_files:
        try:
            df = pd.read_csv(file_path, nrows=3)
            table_name = os.path.basename(file_path)
            schema_context += f"--- Bảng/File: {table_name} ---\n"
            schema_context += f"- Cột & Kiểu dữ liệu: {df.dtypes.astype(str).to_dict()}\n"
            schema_context += f"- Dữ liệu mẫu:\n{df.to_markdown(index=False)}\n\n"
        except Exception as e:
            schema_context += f"--- Lỗi khi đọc file {file_path}: {str(e)} ---\n\n"
    return schema_context


def extract_schema_node(state: DataAgentState):
    file_paths = state.get("file_paths", [])

    # --- CACHE SCHEMA: chỉ đọc lại ổ cứng khi danh sách file THAY ĐỔI ---
    # (Nếu sợ file cùng tên nhưng nội dung đổi, so thêm mtime của từng file)
    cache_hit = (
        state.get("schema_str") is not None
        and file_paths == state.get("schema_file_paths")
    )

    if cache_hit:
        schema_str = state["schema_str"]       # dùng lại, KHÔNG đọc ổ cứng
    else:
        schema_str = _build_schema(file_paths) # lượt đầu / file mới -> trích xuất

    # --- RESET CONTROL STATE: LUÔN chạy mỗi lượt, kể cả khi cache hit ---
    return {
        "schema_str": schema_str,
        "schema_file_paths": file_paths,
        "plan": [], "past_steps": [], "current_step_idx": 0,
        "code": None, "execution_status": None, "execution_error": None,
        "traceback": None, "debug_feedback": None,
        "retry_count": 0, "replan_count": 0,
        "is_sufficient": None, "validation_feedback": None, "final_answer": None,
    }