"""
Delete table 5
"""

import os
import shutil
import zipfile
import logging
from pathlib import Path
from lxml import etree
from dotenv import load_dotenv
from supabase import create_client, Client
import requests
from tqdm import tqdm

# ========================================
# CONFIGURATION
# ========================================

# Load environment variables
load_dotenv()

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def truncate_table5():
    """
    Delete all existing rows from table5 before inserting new data.
    
    This ensures a fresh start with each run.
    Uses a trick with .neq('ndc', '') to delete all rows since we can't
    use .delete() without a filter in Supabase.
    
    Returns:
        bool: True if successful, False otherwise
    """
    print("Truncating table5 (deleting all existing rows)...")
    
    try:
        # Delete all rows by using a filter that matches everything
        # .neq('ndc', '') means "where ndc is not equal to empty string"
        # This matches all rows (including nulls)
        response = supabase.table("table5").delete().neq('ndc', '').execute()
        print("Table5 truncated successfully")
        return True
        
    except Exception as e:
        print(f"Failed to truncate table5: {e}")
        return False

def main():
    truncate_table5()

if __name__ == "__main__":
    main()