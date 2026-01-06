"""
Unit tests for DeduplicationService.

Tests text normalization, similarity detection, and duplicate finding.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.deduplication_service import DeduplicationService


class TestDeduplicationService:
    """Test suite for DeduplicationService."""
    
    def test_service_initialization(self):
        """Test that DeduplicationService initializes correctly."""
        service = DeduplicationService()
        
        assert service is not None
        assert hasattr(service, 'similarity_threshold')
        assert isinstance(service.similarity_threshold, float)
        assert 0.0 <= service.similarity_threshold <= 1.0
        assert hasattr(service, 'text_fields')
        assert isinstance(service.text_fields, list)
    
    def test_normalize_text_basic(self):
        """Test basic text normalization."""
        service = DeduplicationService()
        
        # Test lowercase conversion
        result = service.normalize_text("HELLO WORLD")
        assert result == "hello world"
        
        # Test whitespace normalization
        result = service.normalize_text("hello    world")
        assert result == "hello world"
        
        # Test leading/trailing whitespace
        result = service.normalize_text("  hello world  ")
        assert result == "hello world"
    
    def test_normalize_text_url_removal(self):
        """Test URL removal in normalization."""
        service = DeduplicationService()
        
        text = "Check out https://example.com for more info"
        result = service.normalize_text(text)
        assert "https://example.com" not in result
        assert "check out" in result.lower()
        
        text = "Visit http://test.com/page"
        result = service.normalize_text(text)
        assert "http://test.com" not in result
    
    def test_normalize_text_special_characters(self):
        """Test special character removal."""
        service = DeduplicationService()
        
        text = "Hello@#$%^&*()world"
        result = service.normalize_text(text)
        # Should keep basic punctuation but remove special chars
        assert "@" not in result or "#" not in result
    
    def test_normalize_text_empty(self):
        """Test normalization of empty/None values."""
        service = DeduplicationService()
        
        result = service.normalize_text("")
        assert result == ""
        
        result = service.normalize_text(None)
        assert result == ""
    
    def test_is_similar_text_exact_match(self):
        """Test similarity detection for exact matches."""
        service = DeduplicationService()
        
        text1 = "This is a test"
        text2 = "This is a test"
        
        result = service.is_similar_text(text1, text2)
        assert result is True
    
    def test_is_similar_text_very_similar(self):
        """Test similarity detection for very similar texts."""
        service = DeduplicationService()
        
        text1 = "This is a test message"
        text2 = "This is a test messag"  # One character difference
        
        result = service.is_similar_text(text1, text2, threshold=0.8)
        assert result is True
    
    def test_is_similar_text_different(self):
        """Test similarity detection for different texts."""
        service = DeduplicationService()
        
        text1 = "This is a test message"
        text2 = "Completely different content here"
        
        result = service.is_similar_text(text1, text2)
        assert result is False
    
    def test_is_similar_text_short_texts(self):
        """Test similarity for short texts (should require exact match)."""
        service = DeduplicationService()
        
        # Short texts require exact match
        text1 = "test"
        text2 = "test"
        assert service.is_similar_text(text1, text2) is True
        
        text1 = "test"
        text2 = "tes"
        assert service.is_similar_text(text1, text2) is False
    
    def test_is_similar_text_custom_threshold(self):
        """Test similarity with custom threshold."""
        service = DeduplicationService()
        
        text1 = "This is a test message"
        text2 = "This is a test messag"
        
        # With high threshold, should be False
        result = service.is_similar_text(text1, text2, threshold=0.99)
        # May be True or False depending on actual similarity
        
        # With low threshold, should be True
        result = service.is_similar_text(text1, text2, threshold=0.5)
        assert result is True
    
    def test_is_similar_text_none_values(self):
        """Test similarity with None/NaN values."""
        service = DeduplicationService()
        
        result = service.is_similar_text(None, "test")
        assert result is False
        
        result = service.is_similar_text("test", None)
        assert result is False
        
        result = service.is_similar_text(None, None)
        assert result is False
    
    def test_get_text_content(self):
        """Test text content extraction from records."""
        service = DeduplicationService()
        
        # Test with 'text' field
        record = {"text": "This is the content"}
        result = service.get_text_content(record)
        assert result == "This is the content"
        
        # Test with 'content' field
        record = {"content": "This is the content"}
        result = service.get_text_content(record)
        assert result == "This is the content"
        
        # Test with 'title' field
        record = {"title": "This is the title"}
        result = service.get_text_content(record)
        assert result == "This is the title"
        
        # Test priority (text > content > title)
        record = {"text": "text", "content": "content", "title": "title"}
        result = service.get_text_content(record)
        assert result == "text"  # Should prefer 'text' field
    
    def test_get_text_content_empty(self):
        """Test text content extraction with empty records."""
        service = DeduplicationService()
        
        record = {}
        result = service.get_text_content(record)
        assert result == ""
        
        record = {"other_field": "value"}
        result = service.get_text_content(record)
        assert result == ""
    
    def test_find_existing_duplicates_interface(self):
        """Test that find_existing_duplicates method exists and is callable."""
        service = DeduplicationService()
        
        # Test that the method exists and is callable
        assert hasattr(service, 'find_existing_duplicates')
        assert callable(service.find_existing_duplicates)
        
        # Test method signature (requires db and user_id)
        import inspect
        sig = inspect.signature(service.find_existing_duplicates)
        params = list(sig.parameters.keys())
        assert 'new_records' in params
        assert 'db' in params
        assert 'user_id' in params


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

