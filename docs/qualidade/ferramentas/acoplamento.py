"""Grafo de imports internos do pacote app (acoplamento aferente/eferente por módulo)."""
import ast, pathlib, sys
root = pathlib.Path(sys.argv[1])
mods = {}
for f in root.rglob("*.py"):
    name = ".".join(f.with_suffix("").relative_to(root.parent).parts).removesuffix(".__init__")
    deps = set()
    for node in ast.walk(ast.parse(f.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
            deps.add(node.module)
        elif isinstance(node, ast.Import):
            deps |= {a.name for a in node.names if a.name.startswith("app")}
    mods[name] = deps - {name}
fan_in = {m: sorted(o for o, d in mods.items() if m in d) for m in mods}
print(f"{'módulo':32} Ce(sai) Ca(entra)  depende de")
for m in sorted(mods, key=lambda m: -len(mods[m])):
    print(f"{m:32} {len(mods[m]):^7} {len(fan_in[m]):^9}  {', '.join(sorted(mods[m]))}")
