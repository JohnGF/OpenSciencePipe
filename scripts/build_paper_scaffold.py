import os
import sys
import subprocess

# Ensure repo root is in python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.core.latex_exporter import LaTeXExporter

def build_and_compile():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"
    template = sys.argv[2] if len(sys.argv) > 2 else "both"
    output_path = os.path.abspath(output_dir)
    
    print(f"[INFO] Exporting LaTeX template files ({template}) to: {output_path}")
    exporter = LaTeXExporter(output_path)
    exporter.export_all(template=template)
    print("[OK] LaTeX templates exported successfully!")

    targets = []
    template_lower = template.lower()
    if template_lower in ("ieee", "both", "all"):
        targets.append("paper_scaffold.tex")
    if template_lower in ("elsevier", "both", "all"):
        targets.append("elsevier_paper_scaffold.tex")

    for tex_file in targets:
        scaffold_tex = os.path.join(output_path, tex_file)
        if os.path.exists(scaffold_tex):
            print(f"[INFO] Compiling {scaffold_tex} with pdflatex...")
            try:
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", tex_file],
                    cwd=output_path,
                    check=False
                )
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", tex_file],
                    cwd=output_path,
                    check=False
                )
                pdf_file = tex_file.replace(".tex", ".pdf")
                pdf_path = os.path.join(output_path, pdf_file)
                if os.path.exists(pdf_path):
                    print(f"[OK] PDF compilation complete -> {pdf_path}")
                else:
                    print(f"[WARN] PDF file {pdf_file} not found after compilation.")
            except Exception as e:
                print(f"[ERROR] Compilation error for {tex_file}: {e}")

if __name__ == "__main__":
    build_and_compile()
