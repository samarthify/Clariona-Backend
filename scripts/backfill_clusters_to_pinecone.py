#!/usr/bin/env python3
"""
Backfill active ProcessingClusters from Postgres to Pinecone.

Run this BEFORE flipping use_incremental_clustering=true. If Pinecone is empty
when you flip the flag, every new mention would create a brand new cluster
because there's nothing to match against — thousands of 1-mention clusters.
This script upserts cluster centroids to Pinecone so the incremental assigner
can attach new mentions to existing clusters.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / "config" / ".env")

from src.api.database import SessionLocal
from src.api.models import ProcessingCluster
from src.services.pinecone_client import upsert as pinecone_upsert


def main():
    session = SessionLocal()
    try:
        clusters = (
            session.query(ProcessingCluster)
            .filter(
                ProcessingCluster.status == "active",
                ProcessingCluster.centroid.isnot(None),
            )
            .all()
        )

        print(f"Found {len(clusters)} active clusters to backfill")

        batch = []
        skipped = 0

        for cluster in clusters:
            centroid = cluster.centroid
            if not centroid:
                skipped += 1
                continue
            # Ensure list of floats (JSONB may return list)
            centroid = list(centroid) if not isinstance(centroid, list) else centroid
            if len(centroid) != 1536:
                skipped += 1
                continue

            topic_keys = list(cluster.topic_keys or [])
            if not topic_keys and cluster.topic_key:
                topic_keys = [cluster.topic_key]

            metadata = {
                "user_id": str(cluster.user_id) if cluster.user_id else "null",
                "status": "active",
                "size": cluster.size or 1,
                "topic_keys": topic_keys,
            }
            # Legacy mode filter needs topic_key
            if cluster.topic_key:
                metadata["topic_key"] = cluster.topic_key

            batch.append({
                "id": str(cluster.id),
                "values": centroid,
                "metadata": metadata,
            })

            # Upsert in batches of 100
            if len(batch) >= 100:
                ok = pinecone_upsert(vectors=batch)
                if not ok:
                    print("WARNING: Pinecone upsert failed for batch")
                else:
                    print(f"Upserted {len(batch)} clusters...")
                batch = []

        # Final batch
        if batch:
            ok = pinecone_upsert(vectors=batch)
            if not ok:
                print("WARNING: Pinecone upsert failed for final batch")
            else:
                print(f"Upserted {len(batch)} clusters...")

        backfilled = len(clusters) - skipped
        print(f"Done. Backfilled {backfilled} clusters. Skipped {skipped} (no centroid or wrong dim).")

    finally:
        session.close()


if __name__ == "__main__":
    main()
