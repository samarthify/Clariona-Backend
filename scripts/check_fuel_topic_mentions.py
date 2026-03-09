#!/usr/bin/env python3
"""Check fuel-related topic and its mentions in DB."""

import sys
from pathlib import Path
from dotenv import load_dotenv
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

env_paths = [
    Path(__file__).parent.parent / 'config' / '.env',
    Path(__file__).parent.parent / '.env',
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found")
    sys.exit(1)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
session = Session()

print("=" * 80)
print("FUEL-RELATED TOPIC IN topics TABLE")
print("=" * 80)

# 1. Find topics with fuel/crisis/prices in name
rows = session.execute(text("""
    SELECT topic_key, topic_name, description, keywords, keyword_groups, is_active
    FROM topics
    WHERE LOWER(topic_name) LIKE '%fuel%' OR LOWER(topic_name) LIKE '%crisis%'
       OR LOWER(topic_key) LIKE '%fuel%'
    ORDER BY topic_key
""")).fetchall()

if not rows:
    print("No fuel/crisis topics found. Checking all topics with 'fuel' in name or key...")
    rows = session.execute(text("""
        SELECT topic_key, topic_name, keywords, keyword_groups
        FROM topics
        WHERE LOWER(COALESCE(topic_name,'')) LIKE '%fuel%'
           OR LOWER(COALESCE(topic_key,'')) LIKE '%fuel%'
           OR LOWER(COALESCE(topic_name,'')) LIKE '%petrol%'
        ORDER BY topic_key
    """)).fetchall()

for r in rows:
    print(f"\ntopic_key: {r[0]}")
    print(f"topic_name: {r[1]}")
    if len(r) > 2 and r[2]:
        print(f"description: {(r[2] or '')[:200]}...")
    if len(r) > 3:
        print(f"keywords: {r[3]}")
    if len(r) > 4:
        print(f"keyword_groups: {r[4]}")
    print("-" * 60)

# 2. Mention count per fuel topic
print("\n" + "=" * 80)
print("MENTION COUNTS FOR FUEL TOPICS (mention_topics)")
print("=" * 80)

counts = session.execute(text("""
    SELECT t.topic_key, t.topic_name, COUNT(mt.mention_id) as mention_count
    FROM topics t
    LEFT JOIN mention_topics mt ON t.topic_key = mt.topic_key
    WHERE LOWER(t.topic_name) LIKE '%fuel%' OR LOWER(t.topic_key) LIKE '%fuel%'
       OR LOWER(t.topic_name) LIKE '%crisis%'
    GROUP BY t.topic_key, t.topic_name
    ORDER BY mention_count DESC
""")).fetchall()

for c in counts:
    print(f"  {c[0]} ({c[1]}): {c[2]} mentions")

# 3. Sample mentions for fuel_pricing (or first fuel topic)
fuel_topic = "fuel_pricing"  # default
if counts:
    fuel_topic = counts[0][0]

print("\n" + "=" * 80)
print(f"SAMPLE MENTIONS FOR TOPIC: {fuel_topic} (up to 15)")
print("=" * 80)

samples = session.execute(text("""
    SELECT s.entry_id, LEFT(COALESCE(s.title, s.text, s.description, ''), 120) as preview,
           mt.topic_confidence, mt.keyword_score, mt.embedding_score
    FROM mention_topics mt
    JOIN sentiment_data s ON s.entry_id = mt.mention_id
    WHERE mt.topic_key = :tk
    ORDER BY mt.created_at DESC
    LIMIT 15
"""), {"tk": fuel_topic}).fetchall()

for s in samples:
    conf = s[2] if s[2] is not None else 'N/A'
    kw = s[3] if s[3] is not None else 'N/A'
    emb = s[4] if s[4] is not None else 'N/A'
    print(f"\n  entry_id={s[0]} | conf={conf} | kw={kw} | emb={emb}")
    print(f"  preview: {(s[1] or '')[:150]}...")

# 4. X stream rules (those keywords might be stream rules, not topic keywords)
print("\n" + "=" * 80)
print("X STREAM RULES (tag or value containing 'fuel')")
print("=" * 80)

rules = session.execute(text("""
    SELECT id, value, tag, is_active
    FROM x_stream_rules
    WHERE LOWER(COALESCE(value,'')) LIKE '%fuel%'
       OR LOWER(COALESCE(tag,'')) LIKE '%fuel%'
    ORDER BY id
    LIMIT 30
""")).fetchall()

if rules:
    for r in rules:
        print(f"  id={r[0]} tag='{r[2]}' active={r[3]}")
        print(f"    value: {r[1][:100]}...")
else:
    print("  (No x_stream_rules or table may not exist)")

session.close()
print("\nDone.")
