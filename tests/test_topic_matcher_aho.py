"""
Unit tests for Aho-Corasick topic matcher.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from processing.topic_matcher_aho import TopicMatcherAho, _AHO_AVAILABLE
except ImportError:
    _AHO_AVAILABLE = False
    TopicMatcherAho = None


# Minimal master_topics for testing: simple keywords, OR groups, AND groups
MINIMAL_MASTER_TOPICS = {
    "fuel_pricing": {
        "name": "Fuel Pricing",
        "keywords": ["fuel", "petrol", "diesel", "pump price", "subsidy"],
        "keyword_groups": None,
    },
    "education_funding": {
        "name": "Education Funding",
        "keywords": [],
        "keyword_groups": {
            "groups": [
                {"type": "or", "keywords": ["university", "polytechnic", "school"]},
            ],
            "require_all_groups": False,
        },
    },
    "education_policies": {
        "name": "Education Policies",
        "keywords": [],
        "keyword_groups": {
            "groups": [
                {"type": "and", "keywords": ["bill", "education"]},
                {"type": "and", "keywords": ["policy", "school"]},
            ],
            "require_all_groups": False,
        },
    },
    "education_strict": {
        "name": "Education Strict",
        "keywords": [],
        "keyword_groups": {
            "groups": [
                {"type": "or", "keywords": ["university", "college"]},
                {"type": "and", "keywords": ["funding", "education"]},
            ],
            "require_all_groups": True,
        },
    },
}


@pytest.mark.skipif(not _AHO_AVAILABLE, reason="pyahocorasick not installed")
class TestTopicMatcherAho:
    """Tests for TopicMatcherAho."""

    def test_simple_keywords_match(self):
        """Text with fuel/petrol should match fuel_pricing."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("fuel price hike", max_topics=5)
        topics = [r["topic"] for r in result]
        assert "fuel_pricing" in topics

    def test_simple_keywords_multi_word_phrase(self):
        """Multi-word phrase 'pump price' should match fuel_pricing."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("The pump price increased today")
        topics = [r["topic"] for r in result]
        assert "fuel_pricing" in topics

    def test_or_group_match(self):
        """Text with 'university' should match education_funding (OR group)."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("University funding was cut")
        topics = [r["topic"] for r in result]
        assert "education_funding" in topics

    def test_or_group_polytechnic(self):
        """Text with 'polytechnic' should also match education_funding."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("Polytechnic students protested")
        topics = [r["topic"] for r in result]
        assert "education_funding" in topics

    def test_and_group_both_terms(self):
        """'bill education' should match education_policies (AND group)."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("The education bill passed")
        topics = [r["topic"] for r in result]
        assert "education_policies" in topics

    def test_and_group_one_term_no_match(self):
        """'bill' alone should NOT match education_policies (needs both)."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("The bill was rejected")
        topics = [r["topic"] for r in result]
        assert "education_policies" not in topics

    def test_and_group_alternative_phrase(self):
        """'policy school' should match education_policies (second AND group)."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("School policy changes announced")
        topics = [r["topic"] for r in result]
        assert "education_policies" in topics

    def test_require_all_groups_match(self):
        """'university funding education' matches education_strict (OR + AND)."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("University funding for education increased")
        topics = [r["topic"] for r in result]
        assert "education_strict" in topics

    def test_require_all_groups_no_match(self):
        """'university' alone should NOT match education_strict (needs both groups)."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("University enrollment rose")
        topics = [r["topic"] for r in result]
        assert "education_strict" not in topics

    def test_topic_keys_filter(self):
        """topic_keys_filter restricts results."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match(
            "fuel and university",
            topic_keys_filter=["education_funding"],
            max_topics=10,
        )
        topics = [r["topic"] for r in result]
        assert topics == ["education_funding"]
        assert "fuel_pricing" not in topics

    def test_max_topics_truncation(self):
        """max_topics limits result count."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match(
            "fuel university bill education policy school funding",
            max_topics=2,
        )
        assert len(result) == 2

    def test_return_format(self):
        """Result has TopicClassifier-compatible format."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("fuel price", max_topics=1)
        assert len(result) >= 1
        r = result[0]
        assert "topic" in r
        assert "topic_name" in r
        assert "confidence" in r
        assert "keyword_score" in r
        assert "embedding_score" in r
        assert r["confidence"] == 1.0
        assert r["keyword_score"] == 1.0
        assert r["embedding_score"] == 0.0

    def test_empty_text(self):
        """Empty text returns empty list."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        assert matcher.match("") == []
        assert matcher.match("   ") == []

    def test_no_match(self):
        """Text with no keywords returns empty."""
        matcher = TopicMatcherAho(MINIMAL_MASTER_TOPICS)
        result = matcher.match("The weather is nice today")
        assert result == []
