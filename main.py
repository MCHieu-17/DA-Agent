from dotenv import load_dotenv
load_dotenv()

from graph.graph import app

app.get_graph().draw_mermaid_png(output_file_path="flow.png")