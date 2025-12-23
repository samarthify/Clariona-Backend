#!/usr/bin/env python3
"""Debug script to test the analyzer directly."""

import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "src"))

# Set up environment
os.environ['OPENAI_API_KEY'] = 'your-key-here'  # You'll need to set this

from processing.governance_analyzer import GovernanceAnalyzer

# Test with a sample text
test_text = "The government announced new health policies to improve healthcare services across Nigeria."

analyzer = GovernanceAnalyzer()

try:
    result = analyzer.analyze(test_text)
    print("=== ANALYZER RESULT ===")
    for key, value in result.items():
        print(f"{key}: {value}")
except Exception as e:
    print(f"Error: {e}")
    print("This is expected if OpenAI API key is not set")

