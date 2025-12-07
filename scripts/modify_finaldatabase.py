"""
Automated NDC-DUNS Extraction Pipeline
======================================
This script automates the entire process of:
1. Downloading the DailyMed drug label ZIP file
2. Extracting the ZIP and nested prescription ZIPs
3. Processing XML files to extract NDC-DUNS mappings
4. Inserting data into Supabase database

Author: Samay Patel
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


def truncate_joon_ndc_data():
    """
    Delete all existing rows from joon_ndc_data before inserting new matched data.
    
    This ensures a fresh start with each run of the matching process.
    Uses a trick with .neq('id', 0) to delete all rows since we can't
    use .delete() without a filter in Supabase.
    
    Returns:
        bool: True if successful, False otherwise
    """
    print("Truncating joon_ndc_data (deleting all existing rows)...")
    
    try:
        # Delete all rows by using a filter that matches everything
        # .neq('id', 0) means "where id is not equal to 0"
        # This matches all rows (since id starts at 1 with auto-increment)
        response = supabase.table("joon_ndc_data").delete().neq('id', 0).execute()
        print("joon_ndc_data truncated successfully")
        return True
        
    except Exception as e:
        print(f"Failed to truncate joon_ndc_data: {e}")
        return False


def insert_matched_data_to_joon_ndc_data():
    """
    Insert all matching records from table5 and table7 into joon_ndc_data.
    
    Joins table5 and table7 on matching DUNS values and inserts:
    - ndc, ndc_digits from table5
    - fei, address from table7
    - duns (from either table, they're equal in the join)
    
    This creates a row for EVERY matching combination (not just unique DUNS).
    If table5 has 3 rows with duns='123' and table7 has 2 rows with duns='123',
    this creates 6 rows in joon_ndc_data.
    
    The id column auto-increments for each inserted row.
    """
    print("Fetching ALL data from table5...")
    
    try:
        # Get ALL records from table5 (not just first 1000)
        table5_data = []
        offset = 0
        batch_size = 1000
        
        while True:
            batch = supabase.table("table5").select("*").range(offset, offset + batch_size - 1).execute()
            if not batch.data:
                break
            table5_data.extend(batch.data)
            offset += batch_size
            print(f"Fetched {len(table5_data)} records from table5 so far...")
            if len(batch.data) < batch_size:
                break
        
        print(f"Total fetched from table5: {len(table5_data)} records")
        
        # Get ALL records from table7 (not just first 1000)
        print("Fetching ALL data from table7...")
        table7_data = []
        offset = 0
        
        while True:
            batch = supabase.table("table7").select("*").range(offset, offset + batch_size - 1).execute()
            if not batch.data:
                break
            table7_data.extend(batch.data)
            offset += batch_size
            print(f"Fetched {len(table7_data)} records from table7 so far...")
            if len(batch.data) < batch_size:
                break
        
        print(f"Total fetched from table7: {len(table7_data)} records")
        
        # Create a dictionary for table7 indexed by duns for fast lookup
        table7_by_duns = {}
        for record in table7_data:
            duns = record.get('duns')
            if duns:
                if duns not in table7_by_duns:
                    table7_by_duns[duns] = []
                table7_by_duns[duns].append(record)
        
        # Perform the join in Python
        print("Joining data on matching DUNS...")
        matched_records = []
        
        for t5_record in table5_data:
            duns = t5_record.get('duns')
            if duns and duns in table7_by_duns:
                # For each matching table7 record, create a joined record
                for t7_record in table7_by_duns[duns]:
                    matched_records.append({
                        'ndc': t5_record.get('ndc'),
                        'ndc_digits': t5_record.get('ndc_digits'),
                        'fei': t7_record.get('fei'),
                        'address': t7_record.get('address'),
                        'duns': duns
                    })
        
        print(f"Found {len(matched_records)} matching records")
        
        if len(matched_records) == 0:
            print("No matching records found")
            return True
        
        # Insert matched records in batches
        print("Inserting matched data into joon_ndc_data...")
        batch_size = 1000
        total_inserted = 0
        
        for i in range(0, len(matched_records), batch_size):
            batch = matched_records[i:i + batch_size]
            supabase.table("joon_ndc_data").insert(batch).execute()
            total_inserted += len(batch)
            print(f"Inserted {total_inserted}/{len(matched_records)} records")
        
        print(f"Matched data inserted successfully into joon_ndc_data")
        return True
        
    except Exception as e:
        print(f"Failed to insert matched data: {e}")
        return False


def main():
    truncate_joon_ndc_data()
    insert_matched_data_to_joon_ndc_data()

if __name__ == "__main__":
    main()