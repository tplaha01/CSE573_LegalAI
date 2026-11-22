import json
from pathlib import Path
import torch
import numpy as np
import faiss
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModel

# Define absolute paths relative to repository root
ROOT_DIR = Path(__file__).resolve().parent.parent
CHUNKS_JSONL_PATH = ROOT_DIR / "data" / "processed" / "chunks.jsonl"
VECTOR_STORE_DIR = ROOT_DIR / "vector_store"
MODEL_NAME = "law-ai/InLegalBERT"

def read_jsonl(path):
    """Safely stream chunks from jsonl."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)

def mean_pooling(model_output, attention_mask):
    """Apply mean pooling to get sentence/chunk dense embeddings from token hidden states."""
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
    sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    return sum_embeddings / sum_mask

def main():
    print(f"Loading chunks from {CHUNKS_JSONL_PATH}...")
    if not CHUNKS_JSONL_PATH.exists():
        print("Error: chunks.jsonl not found. Run PDF extraction pipeline first.")
        return

    chunks = list(read_jsonl(CHUNKS_JSONL_PATH))
    if not chunks:
        print("Error: chunks.jsonl is empty.")
        return

    print(f"Loaded {len(chunks)} text chunks for dense indexing.")

    # Setup device (GPU if available, else CPU)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    print(f"Initializing tokenizer and model: {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()

    texts = [c["text"] for c in chunks]
    batch_size = 16
    all_embeddings = []

    print("Generating dense embeddings using InLegalBERT...")
    with torch.no_grad():
        for i in tqdm(range(0, len(texts), batch_size)):
            batch_texts = texts[i:i + batch_size]
            
            encoded_input = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors='pt'
            ).to(device)

            model_output = model(**encoded_input)
            
            # Perform pooling
            sentence_embeddings = mean_pooling(model_output, encoded_input['attention_mask'])
            
            # Normalize embeddings for cosine similarity search via Inner Product index
            sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)
            
            all_embeddings.append(sentence_embeddings.cpu().numpy())

    # Concatenate all embeddings into a single numpy array
    embeddings_matrix = np.vstack(all_embeddings).astype('float32')
    dimension = embeddings_matrix.shape[1]
    print(f"Embedding shape: {embeddings_matrix.shape} (Dimension: {dimension})")

    # ==========================================
    # Build FAISS Index
    # ==========================================
    print("Building FAISS index (IndexFlatIP for cosine similarity)...")
    # IndexFlatIP with normalized vectors computes exact cosine similarity
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings_matrix)
    print(f"Total vectors indexed in FAISS: {index.ntotal}")

   
   
    
    # 1. Save FAISS binary index
    faiss.write_index(index, "inlegalbert_faiss.index")


    # 2. Save metadata mapping (links FAISS integer IDs back to chunk_id, doc_id, and text)
    
    metadata = [
    {
        "faiss_id": idx,
        "chunk_id": c.get("chunk_id"),
        "doc_id": c.get("doc_id"),
        "page": c.get("page"),
        "text": c["text"]
    }
    for idx, c in enumerate(chunks)
]

    with open("chunk_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
   

if __name__ == "__main__":
    main()