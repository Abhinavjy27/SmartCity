import os
import re

pattern = re.compile(r"""(?i)(?:api_key|apikey|secret|token|weatherapi_key|groq_api_key|openaq_api_key)\s*[:=]\s*['"]?([a-zA-Z0-9_\-]{10,})['"]?""")
ignored = {'.git', 'node_modules', '.venv', '__pycache__', 'dist', 'build'}

findings = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ignored]
    for f in files:
        if f.endswith(('.py', '.js', '.jsx', '.json', '.env', '.env.example', '.md', '.txt')):
            p = os.path.join(root, f).replace('\\', '/')
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                    for i, line in enumerate(fh, 1):
                        for m in pattern.finditer(line):
                            val = m.group(1)
                            if val in ('application/json', 'your_groq_api_key', 'your_openaq_api_key', 'your_weatherapi_key'):
                                continue
                            masked = val[:3] + '...' + val[-3:] if len(val) > 6 else '***'
                            findings.append((p, i, masked))
            except Exception:
                pass

print(f"Total hardcoded/configured key findings: {len(findings)}")
for file, line, masked in findings:
    print(f"{file}:{line} -> {masked}")
