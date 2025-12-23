from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import csv
import os
from pathlib import Path
from uuid import UUID

# Import the presidential analyzer
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processing.presidential_sentiment_analyzer import PresidentialSentimentAnalyzer
from processing.presidential_data_processor import PresidentialDataProcessor

# Import database dependencies
from . import models, database
from .database import SessionLocal, get_db
from .auth import get_current_user_id

logger = logging.getLogger("presidential_service")

# Initialize presidential analyzer
presidential_analyzer = PresidentialSentimentAnalyzer("President Bola Tinubu", "Nigeria")
presidential_processor = PresidentialDataProcessor("President Bola Tinubu", "Nigeria")

def save_presidential_analysis_to_csv(processed_records: List[Dict], user_id: str) -> str:
    """
    Save presidential analysis results to CSV file as backup.
    
    Args:
        processed_records: List of processed records with presidential analysis
        user_id: User ID for the analysis
    
    Returns:
        Path to the saved CSV file
    """
    try:
        # Create data/processed directory if it doesn't exist
        processed_dir = Path("data/processed")
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"presidential_analysis_{user_id}_{timestamp}.csv"
        filepath = processed_dir / filename
        
        # Save to CSV
        if processed_records:
            df = pd.DataFrame(processed_records)
            df.to_csv(filepath, index=False)
            logger.info(f"Presidential analysis backup saved to: {filepath}")
            return str(filepath)
        else:
            logger.warning("No processed records to save")
            return ""
            
    except Exception as e:
        logger.error(f"Error saving presidential analysis to CSV: {e}")
        return ""

# Pydantic models for presidential analysis
class PresidentialAnalysisRequest(BaseModel):
    text: str
    source_type: Optional[str] = None
    user_id: Optional[str] = None

class PresidentialAnalysisResponse(BaseModel):
    sentiment_label: str
    sentiment_score: float
    sentiment_justification: str
    analysis_timestamp: str

class PresidentialBatchRequest(BaseModel):
    texts: List[str]
    source_types: Optional[List[str]] = None
    user_id: Optional[str] = None

class PresidentialInsightsRequest(BaseModel):
    user_id: str
    date_range: Optional[Dict[str, str]] = None
    source_filter: Optional[str] = None

class PresidentialPrioritiesUpdate(BaseModel):
    priorities: Dict[str, List[str]]
    user_id: str

# Presidential analysis endpoints
async def analyze_presidential_sentiment(request: PresidentialAnalysisRequest) -> PresidentialAnalysisResponse:
    """
    Analyze a single text from the President's strategic perspective.
    """
    try:
        logger.info(f"Analyzing presidential sentiment for text: {request.text[:100]}...")
        
        result = presidential_analyzer.analyze(request.text, request.source_type)
        
        response = PresidentialAnalysisResponse(
            sentiment_label=result['sentiment_label'],
            sentiment_score=result['sentiment_score'],
            sentiment_justification=result['sentiment_justification'],
            analysis_timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"Presidential analysis completed: {result['sentiment_label']} (confidence: {result['sentiment_score']:.2f})")
        return response
        
    except Exception as e:
        logger.error(f"Error in presidential sentiment analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Presidential analysis failed: {str(e)}")

async def batch_analyze_presidential_sentiment(request: PresidentialBatchRequest) -> List[PresidentialAnalysisResponse]:
    """
    Analyze multiple texts from the President's strategic perspective.
    """
    try:
        logger.info(f"Batch analyzing presidential sentiment for {len(request.texts)} texts")
        
        results = presidential_analyzer.batch_analyze(request.texts, request.source_types)
        
        responses = []
        for result in results:
            response = PresidentialAnalysisResponse(
                sentiment_label=result['sentiment_label'],
                sentiment_score=result['sentiment_score'],
                sentiment_justification=result['sentiment_justification'],
                analysis_timestamp=datetime.now().isoformat()
            )
            responses.append(response)
        
        logger.info(f"Batch presidential analysis completed: {len(responses)} results")
        return responses
        
    except Exception as e:
        logger.error(f"Error in batch presidential sentiment analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch presidential analysis failed: {str(e)}")

async def get_presidential_insights(request: PresidentialInsightsRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get strategic insights from presidential sentiment analysis of stored data.
    """
    try:
        logger.info(f"Generating presidential insights for user: {request.user_id}")
        
        # Query database for sentiment data with presidential analysis
        from uuid import UUID
        user_uuid = UUID(request.user_id)
        query = db.query(models.SentimentData).filter(
            models.SentimentData.user_id == user_uuid,
            models.SentimentData.sentiment_label.isnot(None)
        )
        
        # Apply date range filter if provided
        if request.date_range:
            start_date = datetime.fromisoformat(request.date_range['start'])
            end_date = datetime.fromisoformat(request.date_range['end'])
            query = query.filter(
                models.SentimentData.created_at >= start_date,
                models.SentimentData.created_at <= end_date
            )
        
        # Apply source filter if provided
        if request.source_filter:
            query = query.filter(models.SentimentData.source == request.source_filter)
        
        # Get results
        sentiment_records = query.all()
        
        if not sentiment_records:
            return {
                "error": "No presidential analysis data found",
                "user_id": request.user_id,
                "analysis_timestamp": datetime.now().isoformat()
            }
        
        # Convert to DataFrame for analysis
        data_list = []
        for record in sentiment_records:
            data_list.append({
                'sentiment_label': record.sentiment_label,
                'sentiment_score': record.sentiment_score,
                'sentiment_justification': record.sentiment_justification,
                'source': record.source,
                'text': record.text,
                'title': record.title
            })
        
        data_df = pd.DataFrame(data_list)
        insights = presidential_processor.get_presidential_insights(data_df)
        
        # Add metadata
        insights['analysis_timestamp'] = datetime.now().isoformat()
        insights['user_id'] = request.user_id
        insights['total_records_analyzed'] = len(sentiment_records)
        
        logger.info(f"Presidential insights generated successfully for {len(sentiment_records)} records")
        return insights
        
    except Exception as e:
        logger.error(f"Error generating presidential insights: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Presidential insights generation failed: {str(e)}")

async def update_presidential_priorities(request: PresidentialPrioritiesUpdate) -> Dict[str, Any]:
    """
    Update the presidential priorities and keywords for analysis.
    """
    try:
        logger.info(f"Updating presidential priorities for user: {request.user_id}")
        
        presidential_analyzer.update_presidential_priorities(request.priorities)
        presidential_processor.update_presidential_priorities(request.priorities)
        
        response = {
            "message": "Presidential priorities updated successfully",
            "updated_priorities": list(request.priorities.keys()),
            "timestamp": datetime.now().isoformat(),
            "user_id": request.user_id
        }
        
        logger.info(f"Presidential priorities updated: {list(request.priorities.keys())}")
        return response
        
    except Exception as e:
        logger.error(f"Error updating presidential priorities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Presidential priorities update failed: {str(e)}")

async def generate_presidential_report(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Generate a comprehensive presidential strategic report.
    """
    try:
        logger.info(f"Generating presidential report for user: {user_id}")
        
        # Query database for sentiment data with presidential analysis
        from uuid import UUID
        user_uuid = UUID(user_id)
        sentiment_records = db.query(models.SentimentData).filter(
            models.SentimentData.user_id == user_uuid,
            models.SentimentData.sentiment_label.isnot(None)
        ).all()
        
        if not sentiment_records:
            return {
                "error": "No presidential analysis data found",
                "user_id": user_id,
                "generated_at": datetime.now().isoformat(),
                "report_type": "presidential_strategic_analysis"
            }
        
        # Convert to DataFrame for analysis
        data_list = []
        for record in sentiment_records:
            data_list.append({
                'sentiment_label': record.sentiment_label,
                'sentiment_score': record.sentiment_score,
                'sentiment_justification': record.sentiment_justification,
                'source': record.source,
                'text': record.text,
                'title': record.title
            })
        
        data_df = pd.DataFrame(data_list)
        report = presidential_processor.generate_presidential_report(data_df)
        
        response = {
            "report": report,
            "generated_at": datetime.now().isoformat(),
            "user_id": user_id,
            "report_type": "presidential_strategic_analysis",
            "total_records_analyzed": len(sentiment_records)
        }
        
        logger.info(f"Presidential report generated successfully for {len(sentiment_records)} records")
        return response
        
    except Exception as e:
        logger.error(f"Error generating presidential report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Presidential report generation failed: {str(e)}")

async def get_presidential_metrics(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get key presidential metrics and KPIs.
    """
    try:
        logger.info(f"Getting presidential metrics for user: {user_id}")
        
        # Query database for presidential analysis data
        from uuid import UUID
        user_uuid = UUID(user_id)
        sentiment_records = db.query(models.SentimentData).filter(
            models.SentimentData.user_id == user_uuid,
            models.SentimentData.sentiment_label.isnot(None)
        ).all()
        
        if not sentiment_records:
            return {
                "error": "No presidential analysis data found",
                "user_id": user_id,
                "last_updated": datetime.now().isoformat()
            }
        
        # Calculate metrics
        total_items = len(sentiment_records)
        positive_count = len([r for r in sentiment_records if r.sentiment_label == 'positive'])
        negative_count = len([r for r in sentiment_records if r.sentiment_label == 'negative'])
        neutral_count = len([r for r in sentiment_records if r.sentiment_label == 'neutral'])
        
        # High priority alerts (negative with high confidence)
        high_priority = len([r for r in sentiment_records 
                           if r.sentiment_label == 'negative' 
                           and r.sentiment_score and r.sentiment_score > 0.8])
        
        # Top topics (extract from justification)
        all_topics = []
        for record in sentiment_records:
            if record.sentiment_justification:
                # Extract topics from justification text
                topics = self._extract_topics_from_justification(record.sentiment_justification)
                all_topics.extend(topics)
        
        topic_counts = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Most supportive sources
        source_sentiment = {}
        for record in sentiment_records:
            if record.source:
                if record.source not in source_sentiment:
                    source_sentiment[record.source] = {'positive': 0, 'negative': 0, 'neutral': 0}
                source_sentiment[record.source][record.sentiment_label] += 1
        
        most_supportive_sources = []
        for source, counts in source_sentiment.items():
            if counts['positive'] > counts['negative']:
                most_supportive_sources.append(source)
        
        metrics = {
            "total_items_analyzed": total_items,
            "positive_content": positive_count,
            "negative_content": negative_count,
            "neutral_content": neutral_count,
            "high_priority_alerts": high_priority,
            "top_threatening_topics": [topic for topic, count in top_topics],
            "most_supportive_sources": most_supportive_sources[:5],
            "strategic_recommendations": [
                f"Immediate response required to {negative_count} negative content pieces" if negative_count > 0 else "No immediate threats detected",
                f"Amplify {positive_count} positive content pieces" if positive_count > 0 else "No positive content to amplify",
                f"Monitor {neutral_count} neutral items closely" if neutral_count > 0 else "No neutral items to monitor"
            ],
            "last_updated": datetime.now().isoformat(),
            "user_id": user_id
        }
        
        logger.info(f"Presidential metrics retrieved successfully for {total_items} records")
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting presidential metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Presidential metrics retrieval failed: {str(e)}")

# Add this function to integrate presidential analysis with existing data processing
async def process_existing_data_with_presidential_analysis(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Process existing sentiment data with presidential analysis.
    This function analyzes all existing sentiment data that doesn't have presidential analysis yet.
    """
    try:
        logger.info(f"Processing existing data with presidential analysis for user: {user_id}")
        
        # Get all sentiment records that don't have presidential analysis yet
        from uuid import UUID
        user_uuid = UUID(user_id)
        records_to_analyze = db.query(models.SentimentData).filter(
            models.SentimentData.user_id == user_uuid,
            models.SentimentData.sentiment_label.is_(None)
        ).all()
        
        if not records_to_analyze:
            return {
                "message": "No records found that need presidential analysis",
                "user_id": user_id,
                "processed_count": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        processed_count = 0
        for record in records_to_analyze:
            try:
                # Get text content for analysis
                text_content = record.text or record.content or record.title or record.description
                
                if not text_content:
                    continue
                
                # Perform presidential analysis
                analysis_result = presidential_analyzer.analyze(text_content, record.source_type)
                
                # Update record with presidential analysis using existing fields
                record.sentiment_label = analysis_result['sentiment_label']
                record.sentiment_score = analysis_result['sentiment_score']
                record.sentiment_justification = analysis_result['sentiment_justification']
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing record {record.entry_id}: {e}")
                continue
        
        # Commit changes to database
        db.commit()
        
        response = {
            "message": f"Successfully processed {processed_count} records with presidential analysis",
            "user_id": user_id,
            "processed_count": processed_count,
            "total_records": len(records_to_analyze),
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Presidential analysis completed: {processed_count}/{len(records_to_analyze)} records processed")
        return response
        
    except Exception as e:
        logger.error(f"Error processing existing data with presidential analysis: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Presidential analysis processing failed: {str(e)}")

def deduplicate_sentiment_data(records: List[models.SentimentData]) -> List[models.SentimentData]:
    """
    Deduplicate sentiment data records based on content similarity.
    Uses the same logic as the data processor to ensure consistency.
    """
    if not records:
        return records
    
    logger.info(f"Starting deduplication of {len(records)} records")
    
    # Convert to list of dictionaries for easier processing
    records_dict = []
    for record in records:
        # Get the main text content
        text_content = record.text or record.content or record.title or record.description or ""
        records_dict.append({
            'record': record,
            'text': text_content,
            'normalized_text': normalize_text_for_dedup(text_content)
        })
    
    # Remove exact duplicates based on normalized text
    seen_texts = set()
    unique_records = []
    
    for item in records_dict:
        normalized_text = item['normalized_text']
        if normalized_text not in seen_texts:
            seen_texts.add(normalized_text)
            unique_records.append(item['record'])
    
    logger.info(f"After exact deduplication: {len(unique_records)} records (removed {len(records) - len(unique_records)} duplicates)")
    
    # Remove similar content (simplified version for performance)
    final_records = remove_similar_content(unique_records)
    
    logger.info(f"After similarity deduplication: {len(final_records)} records (removed {len(unique_records) - len(final_records)} similar records)")
    
    return final_records

def normalize_text_for_dedup(text: str) -> str:
    """
    Normalize text for deduplication (same logic as data processor).
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Remove common punctuation that doesn't affect meaning
    import re
    text = re.sub(r'[^\w\s]', '', text)
    
    return text.strip()

def remove_similar_content(records: List[models.SentimentData], similarity_threshold: float = 0.85) -> List[models.SentimentData]:
    """
    Remove records with similar content using a simplified approach.
    """
    if len(records) <= 1:
        return records
    
    # Convert to list of dictionaries for processing
    records_data = []
    for record in records:
        text_content = record.text or record.content or record.title or record.description or ""
        records_data.append({
            'record': record,
            'text': text_content,
            'normalized_text': normalize_text_for_dedup(text_content)
        })
    
    # Simple similarity check based on text length and content overlap
    indices_to_keep = []
    
    for i, item1 in enumerate(records_data):
        keep_record = True
        
        for j in range(i + 1, len(records_data)):
            item2 = records_data[j]
            
            # Skip if we already decided to drop this record
            if j in indices_to_keep:
                continue
            
            # Quick length check
            len1, len2 = len(item1['normalized_text']), len(item2['normalized_text'])
            if len1 == 0 or len2 == 0:
                continue
            
            # Calculate similarity based on common words
            words1 = set(item1['normalized_text'].split())
            words2 = set(item2['normalized_text'].split())
            
            if len(words1) == 0 or len(words2) == 0:
                continue
            
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            if union > 0:
                similarity = intersection / union
                
                # If similarity is high, keep the longer/more detailed record
                if similarity > similarity_threshold:
                    if len(item1['text']) < len(item2['text']):
                        keep_record = False
                        break
                    else:
                        # Mark the other record to be dropped
                        indices_to_keep.append(j)
        
        if keep_record:
            indices_to_keep.append(i)
    
    # Return only the records we decided to keep
    return [records_data[i]['record'] for i in indices_to_keep if i < len(records_data)]

async def update_latest_data_with_presidential_analysis(user_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get data from latest-data endpoint and update the 3 existing fields with presidential analysis.
    This function fetches the latest data and updates sentiment_label, sentiment_score, and sentiment_justification.
    Now uses the authenticated user's target configuration instead of hardcoded search terms.
    """
    try:
        logger.info(f"Updating latest data with presidential analysis for user: {user_id}")
        
        # Get the user's target configuration from database
        from uuid import UUID
        user_uuid = UUID(user_id)  # Convert string back to UUID for database query
        target_config = db.query(models.TargetIndividualConfiguration)\
                         .filter(models.TargetIndividualConfiguration.user_id == user_uuid)\
                         .order_by(models.TargetIndividualConfiguration.created_at.desc())\
                         .first()
        
        if not target_config:
            return {
                "error": f"No target configuration found for user {user_id}. Please configure your target individual first.",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
        
        # Use the user's target configuration instead of hardcoded terms
        search_terms = [target_config.individual_name] + target_config.query_variations
        
        logger.info(f"Using target configuration for user {user_id}: {target_config.individual_name} with {len(target_config.query_variations)} query variations")
        logger.info(f"Search terms: {search_terms}")
        
        # Build search conditions for the user's target individual
        from sqlalchemy import or_, and_
        search_conditions = []
        for term in search_terms:
            if term and term.strip():
                search_conditions.append(
                    or_(
                        models.SentimentData.text.ilike(f"%{term}%"),
                        models.SentimentData.title.ilike(f"%{term}%"),
                        models.SentimentData.content.ilike(f"%{term}%")
                    )
                )
        
        if not search_conditions:
            return {
                "error": f"No valid search terms found for target individual: {target_config.individual_name}",
                "user_id": user_id,
                "target_individual": target_config.individual_name,
                "timestamp": datetime.now().isoformat()
            }
        
        # Combine all search conditions with OR
        combined_search = or_(*search_conditions)
        
        # Get records that mention the user's target individual and need processing
        # This includes:
        # 1. Records without any sentiment data (need basic sentiment analysis)
        # 2. Records with basic sentiment but without "recommended action" (need presidential analysis)
        records_to_update = db.query(models.SentimentData)\
                              .filter(models.SentimentData.user_id == user_uuid)\
                              .filter(combined_search)\
                              .filter(
                                  or_(
                                      # Records without any sentiment data
                                      models.SentimentData.sentiment_label.is_(None),
                                      # Records with sentiment but without "recommended action" in justification
                                      and_(
                                          models.SentimentData.sentiment_label.isnot(None),
                                          or_(
                                              models.SentimentData.sentiment_justification.is_(None),
                                              models.SentimentData.sentiment_justification == "",
                                              ~func.lower(models.SentimentData.sentiment_justification).contains('recommended action')
                                          )
                                      )
                                  )
                              )\
                              .all()
        
        if not records_to_update:
            return {
                "message": f"No records found that mention {target_config.individual_name} and need processing",
                "user_id": user_id,
                "target_individual": target_config.individual_name,
                "processed_count": 0,
                "timestamp": datetime.now().isoformat()
            }
        
        # Separate records into two categories
        records_without_sentiment = [r for r in records_to_update if r.sentiment_label is None]
        records_with_sentiment = [r for r in records_to_update if r.sentiment_label is not None]
        
        logger.info(f"Found {len(records_to_update)} {target_config.individual_name} records to process:")
        logger.info(f"  - {len(records_without_sentiment)} records need basic sentiment analysis")
        logger.info(f"  - {len(records_with_sentiment)} records need presidential analysis")
        
        # Apply deduplication to remove duplicate content before processing
        deduplicated_records = deduplicate_sentiment_data(records_to_update)
        logger.info(f"After deduplication: {len(deduplicated_records)} unique records to process")
        
        processed_count = 0
        updated_records = []
        processed_data_for_csv = []  # Store full data for CSV backup
        batch_size = 50  # Process in smaller batches
        
        for i, record in enumerate(deduplicated_records):
            try:
                # Get text content for analysis
                text_content = record.text or record.content or record.title or record.description
                
                if not text_content:
                    continue
                
                # Perform presidential analysis
                analysis_result = presidential_analyzer.analyze(text_content, record.source_type)
                
                # Store original values for comparison (handle None values)
                original_label = record.sentiment_label
                original_score = record.sentiment_score
                original_justification = record.sentiment_justification
                
                # Update record with presidential analysis using existing fields
                record.sentiment_label = analysis_result['sentiment_label']
                record.sentiment_score = analysis_result['sentiment_score']
                record.sentiment_justification = analysis_result['sentiment_justification']
                
                processed_count += 1
                
                # Track what was updated
                updated_records.append({
                    "entry_id": record.entry_id,
                    "text": text_content[:100] + "..." if len(text_content) > 100 else text_content,
                    "source": record.source,
                    "original_sentiment": original_label or "None",
                    "new_sentiment": analysis_result['sentiment_label'],
                    "original_score": original_score or "None",
                    "new_score": analysis_result['sentiment_score'],
                    "analysis_type": "Basic Sentiment" if original_label is None else "Presidential Analysis"
                })
                
                # Store full record data for CSV backup (matching to_dict() format exactly)
                processed_data_for_csv.append({
                    "title": record.title,
                    "description": record.description,
                    "content": record.content,
                    "url": record.url,
                    "published_date": record.published_date.isoformat() if record.published_date else None,
                    "source": record.source,
                    "source_url": record.source_url,
                    "query": record.query,
                    "language": record.language,
                    "platform": record.platform,
                    "date": record.date.isoformat() if record.date else None,
                    "text": record.text,
                    "file_source": record.file_source,
                    "id": record.original_id,  # Map back to 'id' for consistency
                    "alert_id": record.alert_id,
                    "published_at": record.published_at.isoformat() if record.published_at else None,
                    "source_type": record.source_type,
                    "country": record.country,
                    "favorite": record.favorite,
                    "tone": record.tone,
                    "source_name": record.source_name,
                    "parent_url": record.parent_url,
                    "parent_id": record.parent_id,
                    "children": record.children,
                    "direct_reach": record.direct_reach,
                    "cumulative_reach": record.cumulative_reach,
                    "domain_reach": record.domain_reach,
                    "tags": record.tags,
                    "score": record.score,
                    "alert_name": record.alert_name,
                    "type": record.type,
                    "post_id": record.post_id,
                    "retweets": record.retweets,
                    "likes": record.likes,
                    "user_location": record.user_location,
                    "comments": record.comments,
                    "user_name": record.user_name,
                    "user_handle": record.user_handle,
                    "user_avatar": record.user_avatar,
                    "sentiment_label": record.sentiment_label,  # Updated with presidential analysis
                    "sentiment_score": record.sentiment_score,  # Updated with presidential analysis
                    "sentiment_justification": record.sentiment_justification,  # Updated with presidential analysis
                    # Additional metadata for tracking
                    "presidential_analysis_timestamp": datetime.now().isoformat(),
                    "original_sentiment_label": original_label,
                    "original_sentiment_score": original_score,
                    "original_sentiment_justification": original_justification
                })
                
                # Commit every batch_size records to avoid long transactions
                if (i + 1) % batch_size == 0:
                    db.commit()
                    logger.info(f"Committed batch {i + 1}/{len(deduplicated_records)} records")
                
            except Exception as e:
                logger.error(f"Error processing record {record.entry_id}: {e}")
                continue
        
        # Commit any remaining changes
        db.commit()
        
        # Save processed data to CSV as backup
        csv_filepath = save_presidential_analysis_to_csv(processed_data_for_csv, user_id)
        
        # Count analysis types
        basic_sentiment_count = len([r for r in updated_records if r.get("analysis_type") == "Basic Sentiment"])
        presidential_analysis_count = len([r for r in updated_records if r.get("analysis_type") == "Presidential Analysis"])
        
        response = {
            "message": f"Successfully processed {processed_count} records for {target_config.individual_name}: {basic_sentiment_count} basic sentiment + {presidential_analysis_count} presidential analysis",
            "user_id": user_id,
            "processed_count": processed_count,
            "basic_sentiment_count": basic_sentiment_count,
            "presidential_analysis_count": presidential_analysis_count,
            "total_records_found": len(records_to_update),
            "unique_records_after_dedup": len(deduplicated_records),
            "target_individual": target_config.individual_name,
            "query_variations": target_config.query_variations,
            "updated_records": updated_records[:10],  # Show first 10 for preview
            "csv_backup_file": csv_filepath if csv_filepath else "No backup file created",
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Presidential analysis update completed for user {user_id}: {processed_count}/{len(deduplicated_records)} records updated")
        return response
        
    except Exception as e:
        logger.error(f"Error updating latest data with presidential analysis for user {user_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Presidential analysis update failed: {str(e)}")

# Add this function to get presidential analysis for specific records
async def get_presidential_analysis_for_records(record_ids: List[int], db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Get presidential analysis for specific sentiment data records.
    """
    try:
        logger.info(f"Getting presidential analysis for {len(record_ids)} records")
        
        records = db.query(models.SentimentData).filter(
            models.SentimentData.entry_id.in_(record_ids)
        ).all()
        
        results = []
        for record in records:
            if record.sentiment_label:
                # Return existing analysis
                results.append({
                    "entry_id": record.entry_id,
                    "text": record.text or record.content or record.title,
                    "source": record.source,
                    "sentiment_label": record.sentiment_label,
                    "sentiment_score": record.sentiment_score,
                    "sentiment_justification": record.sentiment_justification
                })
            else:
                # Perform new analysis
                text_content = record.text or record.content or record.title or record.description
                if text_content:
                    analysis_result = presidential_analyzer.analyze(text_content, record.source_type)
                    
                    # Update record using existing fields
                    record.sentiment_label = analysis_result['sentiment_label']
                    record.sentiment_score = analysis_result['sentiment_score']
                    record.sentiment_justification = analysis_result['sentiment_justification']
                    
                    results.append({
                        "entry_id": record.entry_id,
                        "text": text_content,
                        "source": record.source,
                        "sentiment_label": analysis_result['sentiment_label'],
                        "sentiment_score": analysis_result['sentiment_score'],
                        "sentiment_justification": analysis_result['sentiment_justification']
                    })
        
        # Commit changes
        db.commit()
        
        logger.info(f"Presidential analysis retrieved for {len(results)} records")
        return results
        
    except Exception as e:
        logger.error(f"Error getting presidential analysis for records: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Presidential analysis retrieval failed: {str(e)}")

# Helper function to integrate with existing service
def add_presidential_endpoints(app: FastAPI):
    """
    Add presidential analysis endpoints to the main FastAPI app.
    """
    
    @app.post("/presidential/analyze")
    async def analyze_single(request: PresidentialAnalysisRequest):
        """Analyze a single text from the President's perspective."""
        return await analyze_presidential_sentiment(request)
    
    @app.post("/presidential/batch-analyze")
    async def analyze_batch(request: PresidentialBatchRequest):
        """Analyze multiple texts from the President's perspective."""
        return await batch_analyze_presidential_sentiment(request)
    
    @app.post("/presidential/insights")
    async def get_insights(request: PresidentialInsightsRequest, db: Session = Depends(get_db)):
        """Get strategic insights from presidential analysis."""
        return await get_presidential_insights(request)
    
    @app.post("/presidential/priorities")
    async def update_priorities(request: PresidentialPrioritiesUpdate):
        """Update presidential priorities and keywords."""
        return await update_presidential_priorities(request)
    
    @app.get("/presidential/report")
    async def generate_report(db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
        """Generate a comprehensive presidential strategic report for the authenticated user."""
        return await generate_presidential_report(str(user_id), db)
    
    @app.get("/presidential/metrics")
    async def get_metrics(db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
        """Get key presidential metrics and KPIs for the authenticated user."""
        return await get_presidential_metrics(str(user_id), db)
    
    @app.post("/presidential/process-existing")
    async def process_existing_data(db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
        """Process existing sentiment data with presidential analysis for the authenticated user."""
        return await process_existing_data_with_presidential_analysis(str(user_id), db)
    
    @app.post("/presidential/update-latest")
    async def update_latest_data(db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
        """Get data from latest-data endpoint and update the 3 existing fields with presidential analysis for the authenticated user."""
        return await update_latest_data_with_presidential_analysis(str(user_id), db)
    
    @app.post("/presidential/analyze-records")
    async def analyze_specific_records(record_ids: List[int], db: Session = Depends(get_db)):
        """Get presidential analysis for specific sentiment data records."""
        return await get_presidential_analysis_for_records(record_ids, db)
    
    logger.debug("Presidential analysis endpoints added to FastAPI app")


