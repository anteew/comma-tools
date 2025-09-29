#!/usr/bin/env python3
"""Find all OpenPilot dependencies by analyzing import statements."""

import ast
import os
import subprocess
import sys
from pathlib import Path


def find_imports_in_file(filepath: str) -> set[str]:
    """Extract all import statements from a Python file."""
    imports = set()

    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
    except:
        pass

    return imports


def download_and_analyze(url: str, local_path: str) -> set[str]:
    """Download a file and analyze its imports."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    result = subprocess.run(
        ["curl", "-s", url, "-o", local_path],
        capture_output=True
    )

    if result.returncode == 0 and os.path.exists(local_path):
        return find_imports_in_file(local_path)
    return set()


def find_all_openpilot_deps(commit: str = "c085b8af19438956c1559"):
    """Recursively find all OpenPilot dependencies."""
    base_url = f"https://raw.githubusercontent.com/commaai/openpilot/{commit}"
    temp_dir = "/tmp/openpilot_analysis"

    # Start with logreader.py
    to_analyze = ["tools/lib/logreader.py"]
    analyzed = set()
    all_imports = set()
    openpilot_modules = set()

    while to_analyze:
        current = to_analyze.pop(0)
        if current in analyzed:
            continue

        analyzed.add(current)
        local_path = os.path.join(temp_dir, current)
        url = f"{base_url}/{current}"

        print(f"Analyzing: {current}")
        imports = download_and_analyze(url, local_path)
        all_imports.update(imports)

        # Find openpilot-specific imports
        for imp in imports:
            if imp.startswith("openpilot."):
                parts = imp.split(".")
                if len(parts) >= 3:
                    # Convert module path to file path
                    module_path = "/".join(parts[1:]) + ".py"
                    if module_path not in analyzed:
                        to_analyze.append(module_path)

                    # Track the module directories needed
                    if len(parts) >= 2:
                        openpilot_modules.add(parts[1])
                    if len(parts) >= 3:
                        openpilot_modules.add("/".join(parts[1:2]))

    return openpilot_modules, all_imports


if __name__ == "__main__":
    print("Finding all OpenPilot dependencies needed by LogReader...")
    print("=" * 60)

    modules, imports = find_all_openpilot_deps()

    print("\nTop-level OpenPilot directories needed:")
    for module in sorted(modules):
        print(f"  - {module}")

    print("\nAll imports found:")
    openpilot_imports = sorted([i for i in imports if i.startswith("openpilot.")])
    for imp in openpilot_imports:
        print(f"  - {imp}")

    print("\nExternal dependencies:")
    external = sorted([i for i in imports if not i.startswith("openpilot.") and not i.startswith("cereal")])
    for imp in external[:20]:  # Limit output
        print(f"  - {imp}")