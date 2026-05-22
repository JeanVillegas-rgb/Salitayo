import pandas as pd
import random

# --- UNIVERSAL LOGIC GENERATOR ---
# This version uses "Identity Placeholders" and "Gibberish" to force the 
# model to learn GRAMMAR RULES, not TOPIC VOCABULARY.

concepts = [
    ("implementasyon", "paggawa"), ("integrasyon", "pagsasama"), ("pagtatasa", "pag-aaral"),
    ("partisipasyon", "pagsali"), ("komunikasyon", "pag-uusap"), ("kontribusyon", "pagtulong"),
    ("inobasyon", "pagbabago"), ("rehabilitasyon", "pag-aayos"), ("evalwasyon", "pag-check")
]

topics = ["agham", "batas", "edukasyon", "teknolohiya", "lipunan", "kalusugan", "agrikultura", "ekonomiya", "sining", "kasaysayan", "politika", "musika"]

# --- NEW: "Universal Logic" Gibberish ---
# These force the AI to ignore the topic and just follow the structural flip.
gibberish_concepts = ["blargh", "glip-glop", "zorp", "flurgh", "skibidi", "vort-x", "plumbus"]
gibberish_topics = ["al-pha", "be-ta", "gam-ma", "ze-ta", "del-ta"]

all_data = []

# 1. GENERATE REAL-WORLD DIVERSE PAIRS (10,000)
for _ in range(10000):
    c, c_s = random.choice(concepts)
    t = random.choice(topics)
    
    style = random.randint(1, 4)
    if style == 1:
        comp = f"Ang {c} sa {t} ay isang mahalagang hakbang."
        simp = f"• Mag-{c_s} tayo sa {t}.\n• Mahalaga ito para sa lahat."
    elif style == 2:
        comp = f"Dahil sa {t}, isinagawa ang {c}."
        simp = f"• Ginawa ang {c_s} para sa {t}.\n• Nakatulong ito sa atin."
    elif style == 3:
        comp = f"Kailangan ng {c} para sa ikabubuti ng {t}."
        simp = f"• Gawin natin ang {c_s}.\n• Para ito sa {t}."
    else:
        comp = f"Ang {t} ay nangangailangan ng maingat na {c}."
        simp = f"• Pag-aralan natin ang {t}.\n• Kailangan ng {c_s} dito."
    
    all_data.append({"complex": comp, "simple": simp})

# 2. GENERATE GIBBERISH PAIRS (2,000) - THIS IS THE SECRET SAUCE
for _ in range(2000):
    c = random.choice(gibberish_concepts)
    t = random.choice(gibberish_topics)
    
    comp = f"Ang {c} sa {t} ay kailangan para sa progresibong pagbabago."
    simp = f"• Mag-{c} tayo sa {t}.\n• Makakatulong ito sa pagbabago."
    
    all_data.append({"complex": comp, "simple": simp})

# 3. ADD "NOISE" (NATURAL VARIATIONS)
for _ in range(2000):
    c, c_s = random.choice(concepts)
    t = random.choice(topics)
    noise_word = random.choice(["ngayon", "siguro", "lamang", "mismo", "talaga"])
    
    comp = f"Ang {c} {noise_word} sa {t} ay isinasagawa."
    simp = f"• Ginagawa ang {c_s} sa {t}.\n• {noise_word.capitalize()} ito nangyayari."
    
    all_data.append({"complex": comp, "simple": simp})

df = pd.DataFrame(all_data).sample(frac=1)
df.to_csv("tagalog_simplification_dataset.csv", index=False, encoding='utf-8-sig')
print(f"UNIVERSAL LOGIC READY: {len(df)} pairs (Real + Gibberish + Noise) saved!")
