
import pandas as pd
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

# STEP 1: Read processed dataset
folder = Path(__file__).resolve().parent
csv_file = folder / "skillpath_careers_processed.csv"

if not csv_file.exists():
    raise FileNotFoundError(
        f"Processed CSV not found: {csv_file}"
    )

df = pd.read_csv(csv_file)

# Check required columns
required_columns = [
    "career_name",
    "education_required",
    "required_skills"
]

for col in required_columns:
    if col not in df.columns:
        raise ValueError(f"Missing column: {col}")

# STEP 2: Use first 100 records for a small test
df = df.head(100).copy()

# STEP 3: Prepare text for embeddings
texts = (
    "Career: " + df["career_name"].fillna("").astype(str)
    + ". Required skills: "
    + df["required_skills"].fillna("").astype(str)
).tolist()

# STEP 4: Load pretrained embedding model
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

# STEP 5: Generate vectors
embeddings = model.encode(
    texts,
    normalize_embeddings=True,
    show_progress_bar=True
)

print("\n===== EMBEDDING RESULTS =====")
print("Career records:", len(df))
print("Embedding shape:", embeddings.shape)

# STEP 6: Create a sample search query
query = "Python, machine learning and data analysis"

query_embedding = model.encode(
    [query],
    normalize_embeddings=True
)[0]

# STEP 7: Calculate cosine similarity
similarity_scores = embeddings @ query_embedding

# STEP 8: Retrieve top 5 matching career records
top_indices = np.argsort(
    similarity_scores
)[::-1][:5]

print("\nTop 5 Similar Career Records:")

for rank, idx in enumerate(top_indices, start=1):
    print(
        f"{rank}. {df.iloc[idx]['career_name']}"
        f" | Similarity: {similarity_scores[idx]:.3f}"
    )

# STEP 9: Save generated embeddings
output_file = folder / "career_embeddings_sample.npy"
np.save(output_file, embeddings)

print("\nEmbeddings saved to:", output_file)
print("===== TEST COMPLETED =====")
