import os
import pandas as pd

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
new_csv = os.path.join(repo_root, "outputs", "bertopic_clean", "topic_info.csv")
df = pd.read_csv(new_csv)

search_terms = [
    "transformer", "attention", "autoencoder", "gan", "diffusion",
    "kalman", "wavelet", "emd", "tms", "neonatal", "seeg", "afe",
    "biometric", "fnirs", "dry", "impedance", "sleep", "speech"
]

print("=== SPECIALIZED METHODOLOGICAL & HARDWARE CLUSTERS DISCOVERED IN 57K CORPUS ===")
found_topics = []
for term in search_terms:
    matches = df[df["Name"].str.lower().str.contains(term) & (df["Topic"] != -1)]
    for _, r in matches.iterrows():
        if r["Topic"] not in found_topics:
            found_topics.append(r["Topic"])
            print(f"Topic {r['Topic']:3d} (n={r['Count']:4d}) -> {r['Name']}")
