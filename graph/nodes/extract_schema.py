import pandas as pd
import os
from graph.state import DataAgentState

def extract_schema_node(state: DataAgentState):
    # 1. Kiểm tra cache: Nếu đã có schema thì bỏ qua, không đọc lại ổ cứng
    if state.get("schema_str"): 
        return {} # Trả về dict rỗng -> LangGraph giữ nguyên schema cũ

    # 2. Nếu chưa có (chạy lần đầu tiên), tiến hành đọc file CSV
    csv_files = state.get("file_paths", [])
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
            
    # 3. Trả về kết quả để cập nhật vào State (chỉ chạy 1 lần)
    return {"schema_str": schema_context}