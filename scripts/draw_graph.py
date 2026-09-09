"""Explicit diagram export; PNG requires the Mermaid rendering service."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--png", action="store_true")
    args = parser.parse_args()
    from main import app
    root = Path(__file__).resolve().parents[1]
    (root / "flow.mmd").write_text(app.get_graph().draw_mermaid(), encoding="utf-8")
    if args.png:
        app.get_graph().draw_mermaid_png(output_file_path=str(root / "flow.png"))

if __name__ == "__main__":
    main()
