import re
import os
import json

root = "frontend/src"
patterns = [
    re.compile(r"""(?:fetch|request|axios(?:\.get|\.post)?)\s*\(\s*['"`]([^'"`]+)['"`]"""),
    re.compile(r"""['"`](/(?:api|health|monitoring|planning|agents|models|alerts|simulations|recommendations|digital-twin)[^'"`]*)['"`]""")
]

results = []
for dirpath, _, filenames in os.walk(root):
    for f in filenames:
        if f.endswith(('.js', '.jsx', '.ts', '.tsx')):
            p = os.path.join(dirpath, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                for line_idx, line in enumerate(fh, 1):
                    for pat in patterns:
                        for m in pat.finditer(line):
                            url = m.group(1)
                            # skip comments or non-urls
                            if url.startswith("//") or " " in url.strip():
                                continue
                            results.append({
                                "file": p.replace("\\", "/"),
                                "line": line_idx,
                                "target": url,
                                "code": line.strip()
                            })

# Also detect Planning.jsx fetch explicitly
out_file = "docs/frontend_calls_raw.json"
with open(out_file, "w", encoding="utf-8") as out:
    json.dump(results, out, indent=2)

print(f"Extracted {len(results)} call instances, saved to {out_file}")
for r in results:
    print(f"{r['file']}:{r['line']} -> {r['target']}")
