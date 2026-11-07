import os
import ast
import sys

def get_imports(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except Exception:
            return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.add(node.module.split('.')[0])
    return imports

def main():
    src_dir = r"d:\GitHub_Repositories\AI_FOR_EDU_NEW\src"
    all_imports = set()
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".py"):
                all_imports.update(get_imports(os.path.join(root, file)))

    stdlib = sys.stdlib_module_names if hasattr(sys, "stdlib_module_names") else set()
    
    third_party = set()
    for imp in all_imports:
        if imp not in stdlib and imp != "src" and not imp.startswith("_"):
            third_party.add(imp)

    print("\nThird-party imports detected:")
    for imp in sorted(third_party):
        print(imp)

if __name__ == "__main__":
    main()
