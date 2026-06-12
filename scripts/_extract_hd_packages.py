r"""Print the app's pinned HD dependency specs, one per line.

Parses src/tabs/clone_tab.py with `ast` (never imports it — importing pulls in
PySide6) to read _HDDepsInstallWorker.HD_PACKAGES. This keeps CI's HD-deps
install in lockstep with what the shipped app installs, so the smoke test can
never silently test a different (e.g. wrong-transformers) stack.

    python scripts/_extract_hd_packages.py > hd-reqs.txt
"""
import ast
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src", "tabs", "clone_tab.py")


def main() -> int:
    tree = ast.parse(open(_SRC, encoding="utf-8").read(), _SRC)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(t, ast.Name) and t.id == "HD_PACKAGES"
            for t in node.targets
        ):
            continue
        if not isinstance(node.value, ast.List):
            break
        pkgs = [
            el.value for el in node.value.elts
            if isinstance(el, ast.Constant) and isinstance(el.value, str)
        ]
        if not pkgs:
            break
        print("\n".join(pkgs))
        return 0
    print("ERROR: HD_PACKAGES list not found in clone_tab.py", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
