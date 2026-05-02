
import sys
import os
import numpy as np
import joblib
import warnings
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path("/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2")
sys.path.insert(0, str(PROJECT_ROOT))

def test_model(dtype=np.float32):
    model_path = PROJECT_ROOT / "query/models/domain_classifier.joblib"
    
    if not model_path.exists():
        print("Model file not found.")
        return

    print(f"\n--- Testing with {dtype} ---")
    try:
        payload = joblib.load(model_path)
        intent_clf = payload["intent_clf"]
        domain_clf = payload["domain_clf"]
        
        vec = np.random.randn(1, 1024).astype(dtype)
        vec = vec / np.linalg.norm(vec, axis=1, keepdims=True)
        
        print("Predicting intent...")
        p1 = intent_clf.predict_proba(vec)
        
        print("Predicting domain...")
        p2 = domain_clf.predict_proba(vec)
        print("Done.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_model(np.float32)
    test_model(np.float64)
