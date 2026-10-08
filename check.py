"""Run solution.ipynb the way the submission system does.

    python3 check.py [notebook]

Runs every code cell in order, takes the argument of the final play(...),
and writes it to solution.wav. If this works, your submission will run.
Standard library only.
"""
import ast
import json
import math
from pathlib import Path
import sys

from drumkit import SR, save_wav


def run(path):
    data = json.loads(Path(path).read_text())
    # Keep each cell's position in the notebook, counting markdown cells too,
    # so error messages match what you see in Jupyter.
    cells = []
    for number, cell in enumerate(data["cells"], 1):
        source = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        if cell["cell_type"] == "code" and source.strip():
            cells.append((number, source))
    if not cells:
        raise SystemExit("The notebook has no code cells.")

    namespace = {"__name__": "__main__"}
    for number, source in cells:
        tree = ast.parse(source)
        # Playback belongs to Jupyter: skip the IPython import and play() itself.
        tree.body = [node for node in tree.body if not (
            isinstance(node, ast.ImportFrom) and node.module == "IPython.display"
            or isinstance(node, ast.FunctionDef) and node.name == "play"
        )]
        last = number == cells[-1][0]
        if last:
            final = tree.body[-1] if tree.body else None
            if not (isinstance(final, ast.Expr) and isinstance(final.value, ast.Call)
                    and isinstance(final.value.func, ast.Name) and final.value.func.id == "play"):
                raise SystemExit("The last cell must end with play(...).")
            tree.body = tree.body[:-1]
        try:
            exec(compile(tree, f"cell {number}", "exec"), namespace)
            if last:
                call = final.value
                samples = eval(compile(ast.Expression(call.args[0]), f"cell {number}", "eval"), namespace)
                rate = SR
                for keyword in call.keywords:
                    if keyword.arg == "sample_rate":
                        rate = eval(compile(ast.Expression(keyword.value), f"cell {number}", "eval"), namespace)
        except Exception as error:
            raise SystemExit(f"Cell {number} failed: {type(error).__name__}: {error}")
    return list(samples), rate


if __name__ == "__main__":
    notebook = sys.argv[1] if len(sys.argv) > 1 else "solution.ipynb"
    samples, rate = run(notebook)
    if not samples or not all(math.isfinite(x) for x in samples):
        raise SystemExit("play(...) received no audio, or invalid values.")
    save_wav("solution.wav", samples, rate)
    print(f"OK: {len(samples) / rate:.1f} s at {rate} Hz, written to solution.wav")
