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

import restructurer_inference
print("Resolved model dir:", restructurer_inference._resolve_model_dir("default"))
try:
    res = restructurer_inference.predict("Public policy is frequently influenced by the strategic agendas of interest groups. Minorities are marginalized and systemic inequality is perpetuated when legislative decisions are dictated by corporate funding.")
    print("Predict Result:", res)
except Exception as e:
    print("Inference error:", e)
    import traceback
    traceback.print_exc()
