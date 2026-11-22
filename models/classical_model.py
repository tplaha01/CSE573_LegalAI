import json
from pathlib import Path
from itertools import groupby
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import classification_report
import sklearn_crfsuite
from sklearn_crfsuite import metrics as crf_metrics
import joblib

# Define absolute paths (pointing one level up from 'models/' to repository root)
ROOT_DIR = Path(__file__).resolve().parent.parent
SENTENCES_JSONL_PATH = ROOT_DIR / "data" / "processed" / "sentences.jsonl"
SPLIT_MANIFEST_PATH = ROOT_DIR / "split_manifest.json"
MODEL_DIR = ROOT_DIR / "models"

def read_jsonl(path):
    """Safely stream records from a JSONL file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)

def main():
    print(f"Loading sentences from {SENTENCES_JSONL_PATH}...")
    if not SENTENCES_JSONL_PATH.exists():
        print("Error: sentences.jsonl not found. Run PDF extraction pipeline first.")
        return

    sentences = list(read_jsonl(SENTENCES_JSONL_PATH))
    if not sentences:
        print("Error: sentences.jsonl is empty.")
        return

    print(f"Loaded {len(sentences)} total sentences.")

    # 1. Load split manifest if available, otherwise fallback to GroupShuffleSplit
    train_ids, test_ids = set(), set()
    if SPLIT_MANIFEST_PATH.exists():
        print(f"Loading split manifest from {SPLIT_MANIFEST_PATH}...")
        with SPLIT_MANIFEST_PATH.open(encoding="utf-8") as f:
            manifest = json.load(f)
            train_ids = set(manifest.get("train_text_ids", []))
            test_ids = set(manifest.get("test_case_ids", []))
        print(f"Manifest loaded: {len(train_ids)} train doc IDs, {len(test_ids)} test doc IDs.")

    # 2. Filter or split sentences at the case level (preventing information leakage)
    if train_ids and test_ids:
        train_sentences = [s for s in sentences if s["doc_id"] in train_ids]
        test_sentences = [s for s in sentences if s["doc_id"] in test_ids]
    else:
        print("Fallback: Using GroupShuffleSplit for case-level splitting...")
        texts = [s["text"] for s in sentences]
        labels = [s.get("rhetorical_role", "UNKNOWN") for s in sentences]
        doc_ids = [s["doc_id"] for s in sentences]
        
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, test_idx = next(gss.split(texts, labels, groups=doc_ids))
        
        train_sentences = [sentences[i] for i in train_idx]
        test_sentences = [sentences[i] for i in test_idx]

    print(f"Training set: {len(train_sentences)} sentences | Test set: {len(test_sentences)} sentences")

    # Extract actual texts and silver/gold labels from dataset
    X_train_text = [s["text"] for s in train_sentences]
    y_train = [s.get("rhetorical_role", "UNKNOWN") for s in train_sentences]
    X_test_text = [s["text"] for s in test_sentences]
    y_test = [s.get("rhetorical_role", "UNKNOWN") for s in test_sentences]



    # ==========================================
    # Model 1: TF-IDF + Linear SVM Baseline
    # ==========================================
    print("\n--- Training TF-IDF + Linear SVM ---")
    svm_pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(max_features=10000, ngram_range=(1, 2), stop_words='english')),
        ('clf', LinearSVC(random_state=42, dual="auto"))
    ])

    svm_pipeline.fit(X_train_text, y_train)
    y_pred_svm = svm_pipeline.predict(X_test_text)
    
    print("Linear SVM Classification Report:")
    print(classification_report(y_test, y_pred_svm, zero_division=0))

    # ==========================================
    # Model 2: Conditional Random Field (CRF)
    # ==========================================
    print("\n--- Training Conditional Random Field (CRF) ---")
    
    def extract_crf_features(doc_sentences, i):
        text = doc_sentences[i]["text"]
        words = text.split()
        features = {
            'bias': 1.0,
            'word_count': len(words),
            'first_word': words[0].lower() if words else '',
            'has_digit': any(char.isdigit() for char in text),
            'text_lower': text.lower(),
        }
        if i > 0:
            features['-1:text_lower'] = doc_sentences[i-1]["text"].lower()
        else:
            features['BOS'] = True

        if i < len(doc_sentences) - 1:
            features['+1:text_lower'] = doc_sentences[i+1]["text"].lower()
        else:
            features['EOS'] = True

        return features

    def group_into_sequences(sent_list):
        sorted_sents = sorted(sent_list, key=lambda x: x["doc_id"])
        return [list(group) for _, group in groupby(sorted_sents, key=lambda x: x["doc_id"])]

    train_docs = group_into_sequences(train_sentences)
    test_docs = group_into_sequences(test_sentences)

    X_train_seq = [[extract_crf_features(doc, i) for i in range(len(doc))] for doc in train_docs]
    y_train_seq = [[s.get("rhetorical_role", "UNKNOWN") for s in doc] for doc in train_docs]

    X_test_seq = [[extract_crf_features(doc, i) for i in range(len(doc))] for doc in test_docs]
    y_test_seq = [[s.get("rhetorical_role", "UNKNOWN") for s in doc] for doc in test_docs]

    crf = sklearn_crfsuite.CRF(
        algorithm='lbfgs',
        c1=0.1,
        c2=0.1,
        max_iterations=50,
        all_possible_transitions=True
    )
    crf.fit(X_train_seq, y_train_seq)

    y_pred_seq = crf.predict(X_test_seq)
    print("CRF Sequence Classification Report:")
    print(crf_metrics.flat_classification_report(y_test_seq, y_pred_seq, zero_division=0))

    # ==========================================
    # Save Models to Disk
    # ==========================================
    MODEL_DIR.mkdir(parents=True, exist_ok=True)


    joblib.dump(svm_pipeline, "classical_tfidf_svm_classifier.joblib")
  

    joblib.dump(crf, "classical_crf_classifier.joblib")


if __name__ == "__main__":
    main()