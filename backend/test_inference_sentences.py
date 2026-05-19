import os
import sys
from pathlib import Path
import re

sys.path.append(str(Path(__file__).resolve().parent))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salitayo.settings')
try:
    django.setup()
except Exception as e:
    print("Django setup error:", e)

import restructurer_inference

input_text = "Academic achievement gaps are significantly widened when educational funding is directly tied to local property taxes. Disadvantaged students are disproportionately affected, and historical inequities are systematically reinforced across generations."
sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", input_text) if s.strip()]

print("Sentences:", sentences)
results = []
for sentence in sentences:
    res = restructurer_inference.predict(sentence)
    print(f"Sentence prediction for '{sentence}':", res)
    results.append(res["cleaned"])

print("Combined:", " ".join(results))
