import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salitayo.settings')
try:
    django.setup()
except Exception as e:
    print("Django setup error:", e)

from transformers import T5TokenizerFast, AutoModelForSeq2SeqLM
import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model_dir = "C:\\Users\\MY PC\\Downloads\\restructurer\\backend\\models\\t5_restructurer_updated"

print("Loading tokenizer from standard 't5-small'...")
tokenizer = T5TokenizerFast.from_pretrained("t5-small")
print("Tokenizer loaded successfully!")

print("Loading model from local fine-tuned folder...")
model = AutoModelForSeq2SeqLM.from_pretrained(model_dir).to(DEVICE)
print("Model loaded successfully!")

prompt = "restructure: Public policy is frequently influenced by the strategic agendas of interest groups. Minorities are marginalized and systemic inequality is perpetuated when legislative decisions are dictated by corporate funding."
inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)

print("Running inference...")
with torch.no_grad():
    generated = model.generate(**inputs, max_length=128)
output = tokenizer.decode(generated[0], skip_special_tokens=True)
print("Output:", output)
