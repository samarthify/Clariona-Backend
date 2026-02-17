import sys
import time
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processing.topic_classifier import TopicClassifier

def benchmark():
    print("Initializing TopicClassifier...")
    start_init = time.time()
    classifier = TopicClassifier()
    init_time = time.time() - start_init
    print(f"Initialization took {init_time:.4f}s")
    print(f"Loaded {len(classifier.master_topics)} topics.")
    
    # 1. Create a dummy text and random embedding
    text = "The quick brown fox jumps over the lazy dog."
    embedding = np.random.rand(1536).tolist()
    
    # 2. Warmup
    print("\nWarming up...")
    classifier.classify(text, embedding)
    
    # 3. Benchmark Text+Embedding Classification
    iterations = 1000
    print(f"\nBenchmarking classify() with {iterations} iterations...")
    
    start_time = time.time()
    for _ in range(iterations):
        classifier.classify(text, embedding)
    end_time = time.time()
    
    total_time = end_time - start_time
    avg_time = total_time / iterations
    
    print(f"Total time: {total_time:.4f}s")
    print(f"Average time per classification: {avg_time*1000:.4f} ms")
    print(f"Throughput: {iterations/total_time:.2f} items/sec")
    
    # 4. Benchmark Keyword-Only
    print(f"\nBenchmarking keyword-only classify() with {iterations} iterations...")
    start_time = time.time()
    for _ in range(iterations):
        classifier.classify(text)
    end_time = time.time()
    
    total_time = end_time - start_time
    avg_time = total_time / iterations
    
    print(f"Total time: {total_time:.4f}s")
    print(f"Average time per classification: {avg_time*1000:.4f} ms")

if __name__ == "__main__":
    benchmark()
