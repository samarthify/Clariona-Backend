"""
Aho-Corasick-based topic matcher for fast O(n) keyword-to-bucket classification.

Scans text once regardless of topic count; supports keyword_groups AND/OR logic
with post-processing. Drop-in replacement for the keyword-matching portion of TopicClassifier.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import ahocorasick
    _AHO_AVAILABLE = True
except ImportError:
    _AHO_AVAILABLE = False


class TopicMatcherAho:
    """
    Aho-Corasick automaton for topic matching.
    Build once from master_topics; match() is O(n) in text length.
    """

    def __init__(self, master_topics: Dict[str, Dict[str, Any]]) -> None:
        """
        Build the AC automaton from master_topics.

        Args:
            master_topics: Dict of topic_key -> {name, keywords, keyword_groups, ...}
        """
        if not _AHO_AVAILABLE:
            raise ImportError("pyahocorasick is required for TopicMatcherAho. Install with: pip install pyahocorasick")
        self.master_topics = master_topics
        self._automaton, self._phrase_specs, self._group_specs = self._build_automaton()

    def _build_automaton(self) -> Tuple[Any, Dict, Dict]:
        """
        Build AC automaton and metadata for post-processing.

        Returns:
            (automaton, phrase_specs, group_specs)
            phrase_specs: (topic_key, phrase_idx) -> set of terms (for simple AND phrases)
            group_specs: (topic_key, group_idx) -> {type, terms} (for keyword_groups)
        """
        # keyword_lower -> list of payloads
        # payload: ("simple", topic_key, phrase_idx, term) | ("group", topic_key, group_idx, group_type, term)
        keyword_to_payloads: Dict[str, List[Tuple]] = {}
        phrase_specs: Dict[Tuple[str, int], Set[str]] = {}  # (topic_key, phrase_idx) -> terms
        group_specs: Dict[Tuple[str, int], Dict] = {}  # (topic_key, group_idx) -> {type, terms}

        for topic_key, topic_data in self.master_topics.items():
            keyword_groups = topic_data.get("keyword_groups")
            keywords = topic_data.get("keywords") or []

            if keyword_groups and keyword_groups.get("groups"):
                groups = keyword_groups["groups"]
                for group_idx, group in enumerate(groups):
                    group_type = (group.get("type") or "or").lower()
                    kws = group.get("keywords") or []
                    terms = [str(t).strip().lower() for t in kws if t and str(t).strip()]
                    if not terms:
                        continue
                    key = (topic_key, group_idx)
                    group_specs[key] = {"type": group_type, "terms": set(terms)}
                    for term in terms:
                        payload = ("group", topic_key, group_idx, group_type, term)
                        keyword_to_payloads.setdefault(term, []).append(payload)
            else:
                phrase_idx = 0
                for kw in keywords:
                    if not kw or not isinstance(kw, str):
                        continue
                    or_branches = [p.strip() for p in str(kw).split(",") if p.strip()]
                    for phrase in or_branches:
                        terms = [t.strip().lower() for t in phrase.split() if t.strip()]
                        if not terms:
                            continue
                        key = (topic_key, phrase_idx)
                        phrase_specs[key] = set(terms)
                        for term in terms:
                            payload = ("simple", topic_key, phrase_idx, term)
                            keyword_to_payloads.setdefault(term, []).append(payload)
                        phrase_idx += 1

        A = ahocorasick.Automaton()
        for kw, payloads in keyword_to_payloads.items():
            A.add_word(kw, (kw, payloads))
        A.make_automaton()

        return A, phrase_specs, group_specs

    def match(
        self,
        text: str,
        topic_keys_filter: Optional[List[str]] = None,
        max_topics: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Classify text into topics using Aho-Corasick.

        Args:
            text: Text to classify
            topic_keys_filter: If set, only return topics in this list (e.g. for backfill)
            max_topics: Maximum number of topics to return (no limit if very large)

        Returns:
            List of {topic, topic_name, confidence, keyword_score, embedding_score}
        """
        if not text or not text.strip():
            return []
        text_lower = text.lower()

        # Phase 1: Run AC to collect hits
        hits_simple: Dict[Tuple[str, int], Set[str]] = {}  # (topic_key, phrase_idx) -> terms hit
        hits_group: Dict[Tuple[str, int], Set[str]] = {}  # (topic_key, group_idx) -> terms hit

        for _, (_, payloads) in self._automaton.iter(text_lower):
            for p in payloads:
                if p[0] == "simple":
                    _, topic_key, phrase_idx, term = p
                    key = (topic_key, phrase_idx)
                    hits_simple.setdefault(key, set()).add(term)
                else:
                    _, topic_key, group_idx, group_type, term = p
                    key = (topic_key, group_idx)
                    hits_group.setdefault(key, set()).add(term)

        # Phase 2: Determine which topics qualify
        qualifying: Dict[str, str] = {}  # topic_key -> topic_name (for deterministic output)

        for topic_key, topic_data in self.master_topics.items():
            if topic_keys_filter is not None and topic_key not in topic_keys_filter:
                continue

            keyword_groups = topic_data.get("keyword_groups")
            if keyword_groups and keyword_groups.get("groups"):
                require_all = keyword_groups.get("require_all_groups", False)
                group_matches = []
                for key, spec in self._group_specs.items():
                    if key[0] != topic_key:
                        continue
                    hit_terms = hits_group.get(key, set())
                    if spec["type"] == "or":
                        group_match = len(hit_terms) > 0
                    else:
                        group_match = spec["terms"].issubset(hit_terms)
                    group_matches.append(group_match)
                if require_all:
                    qualifies = group_matches and all(group_matches)
                else:
                    qualifies = any(group_matches)
            else:
                qualifies = False
                for key, required in self._phrase_specs.items():
                    if key[0] != topic_key:
                        continue
                    hit_terms = hits_simple.get(key, set())
                    if required.issubset(hit_terms):
                        qualifies = True
                        break

            if qualifies:
                qualifying[topic_key] = topic_data.get("name", topic_key)

        # Phase 3: Build result in same format as TopicClassifier
        result = []
        for topic_key in sorted(qualifying.keys()):
            result.append({
                "topic": topic_key,
                "topic_name": qualifying[topic_key],
                "confidence": 1.0,
                "keyword_score": 1.0,
                "embedding_score": 0.0,
            })

        if topic_keys_filter is not None:
            result = [r for r in result if r["topic"] in topic_keys_filter]

        result.sort(key=lambda x: (-x["confidence"], x["topic"]))
        if max_topics < 999999:
            result = result[:max_topics]
        return result
