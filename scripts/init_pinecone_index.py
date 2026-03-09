#!/usr/bin/env python3
"""
Initialize Pinecone index for incremental clustering.

Creates the index if it does not exist. Idempotent.
Uses env: PINECONE_API_KEY, PINECONE_INDEX_NAME, PINECONE_ENVIRONMENT (optional).

Run with venv: source venv/bin/activate && python scripts/init_pinecone_index.py
"""
import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / "config" / ".env")


def main():
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "clariona-cluster")
    # Dimension 1536 for OpenAI text-embedding-ada-002 / text-embedding-3-small
    dimension = 1536
    metric = "cosine"

    if not api_key:
        print("ERROR: PINECONE_API_KEY not set. Add to config/.env")
        sys.exit(1)

    try:
        from pinecone import Pinecone, ServerlessSpec
    except ImportError:
        try:
            import pinecone
            # Older pinecone-client 2.x
            pinecone.init(api_key=api_key)
            existing = [idx["name"] for idx in pinecone.list_indexes()]
            if index_name in existing:
                print(f"Index '{index_name}' already exists.")
                return 0
            pinecone.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
                spec={"serverless": {"cloud": "aws", "region": "us-east-1"}},
            )
            print(f"Created index '{index_name}' (dim={dimension}, metric={metric})")
            return 0
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    pc = Pinecone(api_key=api_key)
    existing = [idx.name for idx in pc.list_indexes()]

    if index_name in existing:
        print(f"Index '{index_name}' already exists.")
        return 0

    pc.create_index(
        name=index_name,
        dimension=dimension,
        metric=metric,
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    print(f"Created index '{index_name}' (dim={dimension}, metric={metric})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
