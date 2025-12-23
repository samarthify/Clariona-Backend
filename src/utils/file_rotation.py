import os
import shutil
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

def rotate_processed_files(new_csv_path):
    """
    Handles the rotation of processed CSV files:
    1. Moves the current processed_data_old.csv to an archive location if it exists
    2. Renames the current processed_data.csv to processed_data_old.csv
    3. Copies the newly generated CSV file to the dashboard/public folder as processed_data.csv
    
    Args:
        new_csv_path (str): Path to the newly generated CSV file
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Determine project base path (assuming this script is in src/utils)
        base_path = Path(__file__).parent.parent.parent
        
        # Construct absolute paths
        dashboard_public_dir = base_path / "dashboard" / "public"
        archive_dir = base_path / "data" / "processed" / "archive"
        new_csv_path = Path(new_csv_path) # Ensure new_csv_path is a Path object

        # Ensure the dashboard public directory exists
        dashboard_public_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {dashboard_public_dir}")

        # Define file paths using absolute paths
        old_csv_path = dashboard_public_dir / "processed_data_old.csv"
        current_csv_path = dashboard_public_dir / "processed_data.csv"

        # Create archive directory if it doesn't exist
        archive_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured archive directory exists: {archive_dir}")

        # Step 1: Move old CSV to archive if it exists
        if old_csv_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_path = archive_dir / f"processed_data_archive_{timestamp}.csv"
            # Use copy2 to preserve metadata, then remove original if needed (or just move)
            shutil.copy2(old_csv_path, archive_path) 
            logger.info(f"Archived old CSV to: {archive_path}")
            # Consider os.remove(old_csv_path) here if you truly want to move, not just copy

        # Step 2: Rename current processed_data.csv to processed_data_old.csv if it exists
        if current_csv_path.exists():
            # If old_csv_path exists from a previous run (or wasn't removed in step 1), remove it before renaming
            if old_csv_path.exists():
                 try:
                    os.remove(old_csv_path)
                    logger.info(f"Removed existing old CSV before rename: {old_csv_path}")
                 except OSError as e:
                    logger.warning(f"Could not remove existing old CSV {old_csv_path}: {e}")
            
            # Rename current to old using copy then remove for cross-filesystem safety
            try:
                shutil.copy2(current_csv_path, old_csv_path)
                os.remove(current_csv_path) # Remove original after copying
                logger.info(f"Renamed current CSV to old: {current_csv_path} -> {old_csv_path}")
            except Exception as e:
                logger.error(f"Failed to rename {current_csv_path} to {old_csv_path}: {e}")
                # Attempt to clean up if copy succeeded but remove failed
                if old_csv_path.exists() and not current_csv_path.exists():
                    logger.warning("Original file removed but rename logged error. State might be inconsistent.")
                elif old_csv_path.exists() and current_csv_path.exists():
                     logger.warning("Copy to old path succeeded, but removal of original failed. Cleaning up copied old file.")
                     os.remove(old_csv_path)
                return False # Stop processing if rename fails

        # Step 3: Copy new CSV to dashboard/public as processed_data.csv
        if not new_csv_path.exists():
             logger.error(f"New CSV file not found at {new_csv_path}")
             return False
             
        shutil.copy2(new_csv_path, current_csv_path)
        logger.info(f"Copied new CSV to dashboard: {new_csv_path} -> {current_csv_path}")

        return True

    except Exception as e:
        logger.error(f"Error rotating processed files: {str(e)}", exc_info=True) # Add exc_info for details
        return False

if __name__ == "__main__":
    # For testing purposes
    logging.basicConfig(level=logging.INFO)
    # Example usage: rotate_processed_files("data/processed/latest.csv")
    print("This module is for importing. Run through the main agent process.") 