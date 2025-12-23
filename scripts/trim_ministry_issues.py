#!/usr/bin/env python3
"""
Script to trim all ministry issue files to max 20 issues per ministry.
Keeps the top 20 issues by mention_count.
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def trim_ministry_issues(ministry_issues_dir: str = "ministry_issues", max_issues: int = 20):
    """Trim all ministry JSON files to max_issues, keeping top issues by mention_count."""
    base_path = Path(__file__).parent.parent
    issues_dir = base_path / ministry_issues_dir
    
    if not issues_dir.exists():
        logger.error(f"Directory {issues_dir} does not exist")
        return
    
    trimmed_count = 0
    total_issues_removed = 0
    
    for json_file in sorted(issues_dir.glob("*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            existing_issues = data.get('issues', [])
            current_count = len(existing_issues)
            max_issues_config = data.get('max_issues', max_issues)
            
            if current_count > max_issues_config:
                # Sort by mention_count (descending) and keep top N
                existing_issues.sort(key=lambda x: x.get('mention_count', 0), reverse=True)
                trimmed_issues = existing_issues[:max_issues_config]
                removed_count = current_count - max_issues_config
                
                # Update data
                data['issues'] = trimmed_issues
                data['issue_count'] = len(trimmed_issues)
                data['max_issues'] = max_issues_config
                
                # Save back to file
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                ministry_name = data.get('ministry', json_file.stem)
                logger.info(f"✓ {ministry_name}: Trimmed from {current_count} to {max_issues_config} issues (removed {removed_count})")
                trimmed_count += 1
                total_issues_removed += removed_count
            else:
                # Ensure max_issues is set correctly even if under limit
                if data.get('max_issues') != max_issues_config:
                    data['max_issues'] = max_issues_config
                    data['issue_count'] = len(existing_issues)
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    logger.debug(f"  {json_file.stem}: Updated max_issues to {max_issues_config} (had {current_count} issues)")
        
        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Summary: Trimmed {trimmed_count} ministries, removed {total_issues_removed} excess issues")
    logger.info(f"{'='*60}")

if __name__ == "__main__":
    trim_ministry_issues()


