import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / "frontend" / "src" / "WordProficiency.jsx"
raw = subprocess.check_output(
    ["git", "show", "origin/main:src/components/WordProficiency.jsx"],
    cwd=root,
)
text = raw.decode("utf-8", errors="replace")
text = text.replace("from '../services/api'", "from './services/wpApi'")
text = text.replace('from "../services/api"', "from './services/wpApi'")
out.write_text(text, encoding="utf-8")
print(f"Wrote {out} ({len(text)} chars)")
