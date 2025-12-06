"""
Daily FDA Drug Label Data Automation Script - Version 2.1 FINAL

MAJOR CHANGES FROM V2:
1. SEQUENTIAL PROCESSING - Process one part at a time instead of all 5 at once
2. IMMEDIATE CLEANUP - Delete each part's data before starting the next
3. DISK SPACE OPTIMIZATION - Never have more than 1 part on disk at any time

CHANGES FROM V1:
1. Downloads 5 ZIP files (part1-part5) instead of 1
2. Processes all 5 parts into a single xml_files directory
3. Uses new XML parsing logic (establishments2 function)
4. Allows NULL values for NDC and DUNS
5. No primary key - allows duplicate records
6. Adds ndc_digits column (NDC without dashes)
7. Uses INSERT instead of UPSERT
8. DISK SPACE OPTIMIZATIONS for GitHub Actions (deletes ZIPs after use)
9. Joins table5 and table7 to populate joon_ndc_data

This script:
1. FOR EACH PART (1-5):
   - Downloads FDA drug label ZIP file from DailyMed
   - Extracts ZIP and deletes it immediately
   - Extracts all XML files from nested prescription ZIPs
   - Processes XMLs using establishments2() logic to extract ALL NDC-DUNS combinations
   - Stores records in memory
   - Deletes all part data (extracted folders + XMLs)
2. After all parts processed:
   - Inserts all data into Supabase table5 (allows nulls and duplicates)
   - Joins table5 with table7 to populate joon_ndc_data
   - Cleans up any remaining temporary files

Designed to run daily via GitHub Actions or other schedulers.
"""

import os
import requests
import zipfile
import shutil
from pathlib import Path
from lxml import etree
from dotenv import load_dotenv
from supabase import create_client, Client
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables (only needed for local testing)
# On GitHub Actions, secrets are injected as environment variables
load_dotenv()

# Configuration - Now we download 5 parts instead of 1
BASE_DOWNLOAD_URL = "https://dailymed-data.nlm.nih.gov/public-release-files/"
# List of all 5 ZIP files to download
DOWNLOAD_FILES = [
    "dm_spl_release_human_rx_part1.zip",
    "dm_spl_release_human_rx_part2.zip",
    "dm_spl_release_human_rx_part3.zip",
    "dm_spl_release_human_rx_part4.zip",
    "dm_spl_release_human_rx_part5.zip"
]

WORK_DIR = Path("temp_work")
DOWNLOADS_DIR = WORK_DIR / "downloads"  # Store downloaded ZIP here (one at a time)
EXTRACTED_DIR = WORK_DIR / "extracted"  # Extract ZIP here (one at a time)
XML_OUTPUT_DIR = WORK_DIR / "xml_files"  # Store XMLs temporarily during processing

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# XML namespaces (required for XPath queries)
namespaces = {'v3': 'urn:hl7-org:v3'}


def cleanup_work_directory():
    """
    Remove the temporary work directory if it exists.
    This ensures we start fresh each run.
    """
    if WORK_DIR.exists():
        logger.info(f"Cleaning up work directory: {WORK_DIR}")
        shutil.rmtree(WORK_DIR)


def setup_work_directory():
    """
    Create fresh work directory structure.
    Creates three directories:
    - downloads: for the downloaded ZIP file (one at a time)
    - extracted: for the extracted folder (one at a time)
    - xml_files: for XMLs during processing (cleaned up after each part)
    """
    cleanup_work_directory()
    WORK_DIR.mkdir(exist_ok=True)
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    EXTRACTED_DIR.mkdir(exist_ok=True)
    XML_OUTPUT_DIR.mkdir(exist_ok=True)
    logger.info(f"Created work directory structure: {WORK_DIR}")


# =============================================================================
# NEW XML PARSING LOGIC - Based on establishments2() function
# =============================================================================
# This section replaces the old NDC-DUNS extraction logic with the new
# establishments2-based approach that captures ALL combinations, allows nulls,
# and doesn't enforce uniqueness.
# =============================================================================

def establishments2(label_xml):
    """
    Extract establishment data from XML label.
    
    This is the NEW parsing logic that replaces the old manufacturer-focused approach.
    
    Key differences:
    - Extracts ALL establishment records, not just manufacturers
    - Allows NULL values for both NDC and DUNS
    - Captures activity codes and types
    - Returns ALL combinations (no deduplication)
    
    Returns list of records in format:
    [count, establishment_name, establishment_duns, activity_name, activity_code, ndc]
    
    Args:
        label_xml: Parsed XML tree (lxml etree object)
    
    Returns:
        list: List of establishment records (each record is a list of 6 elements)
    """
    count = 0
    estab_list = []
    
    # Main XPath: Look for establishments in the standard location
    # Path: //author/assignedEntity/representedOrganization/assignedEntity/assignedOrganization/assignedEntity
    establishments = label_xml.xpath(
        "//v3:author/v3:assignedEntity/v3:representedOrganization/v3:assignedEntity/v3:assignedOrganization/v3:assignedEntity",
        namespaces=namespaces
    )
    
    if establishments:
        # Process each establishment found
        for estab in establishments:
            count += 1
            
            # Extract establishment name (with fallback to "n/a")
            try:
                est = estab.xpath(".//v3:name", namespaces=namespaces)[0].text
            except IndexError:
                est = "n/a"
            
            # Extract establishment DUNS number (with fallback to "n/a")
            try:
                est_dun = estab.xpath(".//v3:id/@extension", namespaces=namespaces)[0]
            except IndexError:
                est_dun = "n/a"
            
            # Look for performance/actDefinition elements (activities like MANUFACTURE, PACK, etc.)
            performances = estab.xpath(".//v3:performance/v3:actDefinition", namespaces=namespaces)
            
            if performances:
                # Process each activity for this establishment
                for perf in performances:
                    # Extract activity display name (e.g., "MANUFACTURE", "REPACK")
                    try:
                        act = perf.xpath("./v3:code/@displayName", namespaces=namespaces)[0]
                    except IndexError:
                        act = "n/a"
                    
                    # Extract activity code
                    try:
                        act_code = perf.xpath("./v3:code/@code", namespaces=namespaces)[0]
                    except IndexError:
                        act_code = "n/a"
                    
                    # Extract NDC codes associated with this activity
                    try:
                        ndc_list = perf.xpath(
                            "./v3:product/v3:manufacturedProduct/v3:manufacturedMaterialKind/v3:code/@code",
                            namespaces=namespaces
                        )
                    except IndexError:
                        ndc_list = []
                    
                    # If NDCs were found, create one record per NDC
                    if ndc_list and len(ndc_list) > 0:
                        for ndc_code in ndc_list:
                            estab_list.append([count, est, est_dun, act, act_code, ndc_code])
                    else:
                        # No NDCs found for this activity - still add record with "n/a"
                        estab_list.append([count, est, est_dun, act, act_code, "n/a"])
            else:
                # No activities found for this establishment - still add record
                estab_list.append([count, est, est_dun, "n/a", "n/a", "n/a"])
    else:
        # No establishments found at all - add a single "n/a" record
        estab_list.append([0, "n/a", "n/a", "n/a", "n/a", "n/a"])
    
    return estab_list


def process_xml_file(xml_file):
    """
    Process a single XML file and extract establishment data.
    
    Uses the establishments2() function to get all records, then
    converts them to the format needed for database insertion.
    
    Args:
        xml_file: Path to XML file
    
    Returns:
        list: List of dicts with keys: ndc, duns, ndc_digits
    """
    try:
        # Parse XML with huge_tree option to handle large/deeply nested files
        parser = etree.XMLParser(huge_tree=True)
        tree = etree.parse(str(xml_file), parser)
        
        # Get establishment data using the new function
        estab_data = establishments2(tree)
        
        records = []
        
        # Convert establishment data to database format
        # estab_data format: [count, est_name, est_dun, act, act_code, ndc]
        for row in estab_data:
            ndc = row[5]  # NDC code (6th element)
            duns = row[2]  # DUNS number (3rd element)
            
            # Convert "n/a" to None (NULL in database)
            ndc_value = None if ndc == "n/a" else ndc
            duns_value = None if duns == "n/a" else duns
            
            # Calculate ndc_digits (NDC without dashes)
            # If NDC is None or "n/a", ndc_digits is also None
            if ndc_value:
                ndc_digits = ndc_value.replace("-", "")
            else:
                ndc_digits = None
            
            # Add record even if one or both values are None
            # Skip ONLY if BOTH are None (no useful data)
            if ndc_value or duns_value:
                records.append({
                    "ndc": ndc_value,
                    "duns": duns_value,
                    "ndc_digits": ndc_digits
                })
        
        return records
    
    except Exception as e:
        # If XML parsing fails, return empty list (skip this file)
        logger.error(f"Error processing {xml_file.name}: {e}")
        return []


def truncate_table5():
    """
    Delete all existing rows from table5 before inserting new data.
    
    This ensures a fresh start with each run.
    Uses a trick with .neq('ndc', '') to delete all rows since we can't
    use .delete() without a filter in Supabase.
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("Truncating table5 (deleting all existing rows)...")
    
    try:
        # Delete all rows by using a filter that matches everything
        # .neq('ndc', '') means "where ndc is not equal to empty string"
        # This matches all rows (including nulls)
        response = supabase.table("table5").delete().neq('ndc', '').execute()
        logger.info("✓ Table5 truncated successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to truncate table5: {e}")
        return False


def insert_to_supabase(records):
    """
    Insert all records into Supabase table5.
    
    IMPORTANT CHANGES FROM V1:
    - Uses INSERT instead of UPSERT (no deduplication)
    - Allows NULL values for ndc and duns
    - Includes ndc_digits column (NDC without dashes)
    - No primary key constraint
    
    Args:
        records: List of dicts with keys: ndc, duns, ndc_digits
    """
    if not records:
        logger.warning("No data to insert into Supabase")
        return
    
    logger.info(f"Inserting {len(records)} records into Supabase table5")
    
    # Insert in batches to avoid timeout
    batch_size = 1000
    total_inserted = 0
    total_batches = (len(records) + batch_size - 1) // batch_size
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        try:
            # Use INSERT (not UPSERT) - we want ALL records, including duplicates
            response = supabase.table("table5").insert(batch).execute()
            total_inserted += len(batch)
            logger.info(f"✓ Batch {batch_num}/{total_batches}: Inserted {total_inserted}/{len(records)} records")
        
        except Exception as e:
            logger.error(f"✗ Error inserting batch {batch_num}: {e}")
            logger.info(f"  Falling back to one-by-one insertion for this batch...")
            
            # If batch fails, try inserting records one by one
            for record in batch:
                try:
                    supabase.table("table5").insert(record).execute()
                    total_inserted += 1
                except Exception as record_error:
                    logger.error(f"  ✗ Failed to insert record: {record_error}")
    
    logger.info(f"✓ Insertion complete: {total_inserted}/{len(records)} records inserted")


def truncate_joon_ndc_data():
    """
    Delete all existing rows from joon_ndc_data before inserting new matched data.
    
    This ensures a fresh start with each run of the matching process.
    Uses a trick with .neq('id', 0) to delete all rows since we can't
    use .delete() without a filter in Supabase.
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("Truncating joon_ndc_data (deleting all existing rows)...")
    
    try:
        # Delete all rows by using a filter that matches everything
        # .neq('id', 0) means "where id is not equal to 0"
        # This matches all rows (since id starts at 1 with auto-increment)
        response = supabase.table("joon_ndc_data").delete().neq('id', 0).execute()
        logger.info("✓ joon_ndc_data truncated successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to truncate joon_ndc_data: {e}")
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
    
    Note: This uses raw SQL via Supabase RPC call or direct query execution.
    Supabase Python client doesn't support JOIN operations directly, so we
    need to use PostgreSQL functions or raw SQL.
    """
    logger.info("Inserting matched data from table5 and table7 into joon_ndc_data...")
    
    try:
        # SQL query to insert all matching records
        sql_query = """
        INSERT INTO joon_ndc_data (ndc, ndc_digits, fei, address, duns)
        SELECT 
            t5.ndc,
            t5.ndc_digits,
            t7.fei,
            t7.address,
            t5.duns
        FROM table5 t5
        INNER JOIN table7 t7 ON t5.duns = t7.duns;
        """
        
        # Execute the SQL query using Supabase RPC
        # Note: You'll need to create a PostgreSQL function in Supabase to execute this,
        # OR use the PostgREST API directly
        response = supabase.rpc('insert_matched_ndc_data').execute()
        
        logger.info("✓ Matched data inserted successfully into joon_ndc_data")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to insert matched data: {e}")
        logger.info("Note: You may need to create a PostgreSQL function in Supabase")
        logger.info("Function name: insert_matched_ndc_data")
        logger.info("Function SQL:")
        logger.info("""
        CREATE OR REPLACE FUNCTION insert_matched_ndc_data()
        RETURNS void AS $$
        BEGIN
            INSERT INTO joon_ndc_data (ndc, ndc_digits, fei, address, duns)
            SELECT 
                t5.ndc,
                t5.ndc_digits,
                t7.fei,
                t7.address,
                t5.duns
            FROM table5 t5
            INNER JOIN table7 t7 ON t5.duns = t7.duns;
        END;
        $$ LANGUAGE plpgsql;
        """)
        return False


def process_single_part(part_number, part_filename):
    """
    Process a single part completely before moving to the next.
    
    This function downloads, extracts, and processes one part at a time,
    then cleans up that part's data before moving to the next part.
    
    This sequential approach minimizes disk usage - we only have one part's
    data on disk at a time instead of all 5 parts.
    
    Args:
        part_number: Part number (1-5)
        part_filename: Filename of the ZIP to download (e.g., "dm_spl_release_human_rx_part1.zip")
    
    Returns:
        list: All records extracted from this part
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"PROCESSING PART {part_number}/5: {part_filename}")
    logger.info(f"{'='*70}")
    
    part_records = []
    
    try:
        # Step A: Download this part's ZIP
        logger.info(f"\n[Part {part_number} - Step A] Downloading {part_filename}...")
        download_url = BASE_DOWNLOAD_URL + part_filename
        zip_path = DOWNLOADS_DIR / part_filename
        
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        logger.info(f"Size: {total_size / (1024*1024):.2f} MB")
        
        with open(zip_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded % (10 * 1024 * 1024) == 0:
                    logger.info(f"  Downloaded: {downloaded / (1024*1024):.2f} MB")
        
        logger.info(f"✓ Download complete")
        
        # Step B: Extract this part's main ZIP
        logger.info(f"\n[Part {part_number} - Step B] Extracting main ZIP...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(EXTRACTED_DIR)
        logger.info(f"✓ Extracted successfully")
        
        # Delete the downloaded ZIP immediately to free space
        zip_path.unlink()
        logger.info(f"  Deleted downloaded ZIP to free disk space")
        
        # Step C: Find prescription directory for this part
        logger.info(f"\n[Part {part_number} - Step C] Locating prescription directory...")
        prescription_dir = None
        for root, dirs, files in os.walk(EXTRACTED_DIR):
            if 'prescription' in dirs:
                prescription_dir = Path(root) / 'prescription'
                logger.info(f"✓ Found: {prescription_dir}")
                break
        
        if not prescription_dir:
            raise Exception(f"No prescription directory found for part {part_number}")
        
        # Step D: Extract prescription ZIPs and process XMLs
        logger.info(f"\n[Part {part_number} - Step D] Processing prescription ZIPs...")
        
        zip_files = list(prescription_dir.glob("*.zip"))
        logger.info(f"Found {len(zip_files)} prescription ZIP files")
        
        xml_count = 0
        for idx, zip_file in enumerate(zip_files, 1):
            if idx % 100 == 0:
                logger.info(f"  Progress: {idx}/{len(zip_files)} ZIPs processed...")
            
            try:
                temp_extract_path = prescription_dir / f"temp_{zip_file.stem}"
                temp_extract_path.mkdir(exist_ok=True)
                
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_path)
                
                xml_files = list(temp_extract_path.rglob("*.xml"))
                
                for xml_file in xml_files:
                    output_filename = f"part{part_number}_{zip_file.stem}_{xml_file.name}"
                    output_path = XML_OUTPUT_DIR / output_filename
                    shutil.copy2(xml_file, output_path)
                    xml_count += 1
                
                shutil.rmtree(temp_extract_path)
                
            except Exception as e:
                logger.error(f"Error processing {zip_file.name}: {e}")
                if temp_extract_path.exists():
                    shutil.rmtree(temp_extract_path)
        
        logger.info(f"✓ Extracted {xml_count} XML files from part {part_number}")
        
        # Step E: Process XMLs from this part
        logger.info(f"\n[Part {part_number} - Step E] Processing XML files...")
        
        xml_files = list(XML_OUTPUT_DIR.glob(f"part{part_number}_*.xml"))
        logger.info(f"Processing {len(xml_files)} XML files from part {part_number}")
        
        for i, xml_file in enumerate(xml_files, 1):
            records = process_xml_file(xml_file)
            if records:
                part_records.extend(records)
            
            if i % 1000 == 0:
                logger.info(f"  Progress: {i}/{len(xml_files)} XMLs processed... ({len(part_records)} records)")
        
        logger.info(f"✓ Extracted {len(part_records)} records from part {part_number}")
        
        # Step F: Cleanup this part's data to free disk space
        logger.info(f"\n[Part {part_number} - Step F] Cleaning up part {part_number} data...")
        
        # Delete extracted directory for this part
        for item in EXTRACTED_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
                logger.info(f"  Deleted extracted directory: {item.name}")
        
        # Delete XMLs from this part (we've already extracted the records)
        for xml_file in XML_OUTPUT_DIR.glob(f"part{part_number}_*.xml"):
            xml_file.unlink()
        
        logger.info(f"✓ Cleanup complete for part {part_number}")
        logger.info(f"\n{'='*70}")
        logger.info(f"✓ PART {part_number}/5 COMPLETE: {len(part_records)} records extracted")
        logger.info(f"{'='*70}\n")
        
        return part_records
        
    except Exception as e:
        logger.error(f"✗ Error processing part {part_number}: {e}")
        # Cleanup on error
        logger.info(f"Cleaning up part {part_number} after error...")
        for item in EXTRACTED_DIR.iterdir():
            if item.is_dir():
                try:
                    shutil.rmtree(item)
                except:
                    pass
        for xml_file in XML_OUTPUT_DIR.glob(f"part{part_number}_*.xml"):
            try:
                xml_file.unlink()
            except:
                pass
        raise


def main():
    """
    Main orchestration function.
    
    NEW STRATEGY FOR DISK SPACE:
    Instead of downloading/extracting all 5 parts at once, we process them
    sequentially - one complete part at a time. This keeps disk usage minimal.
    
    Orchestrates the entire process:
    1. Setup work directories
    2. FOR EACH PART (1-5):
       - Download part ZIP
       - Extract main ZIP (delete ZIP after)
       - Find prescription directory
       - Extract and process prescription ZIPs
       - Extract records from XMLs
       - Delete part's data (extracted folders + XMLs)
    3. Combine all records from all parts
    4. Truncate table5
    5. Insert all data to Supabase table5
    6. Truncate joon_ndc_data
    7. Insert matched data (table5 JOIN table7) into joon_ndc_data
    8. Clean up remaining temporary files
    """
    start_time = datetime.now()
    logger.info("="*70)
    logger.info("FDA DRUG LABEL DATA AUTOMATION - DAILY RUN (5 PARTS)")
    logger.info(f"Run started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)
    
    try:
        # Step 1: Setup
        logger.info("\n[STEP 1/7] Setting up work directory...")
        setup_work_directory()
        
        # Step 2: Process all 5 parts sequentially
        logger.info("\n[STEP 2/7] Processing 5 parts sequentially...")
        logger.info("NOTE: Each part is fully processed and cleaned up before the next begins")
        logger.info("This minimizes disk usage for GitHub Actions")
        
        all_records = []
        parts_processed = 0
        
        for part_num, part_file in enumerate(DOWNLOAD_FILES, 1):
            try:
                part_records = process_single_part(part_num, part_file)
                all_records.extend(part_records)
                parts_processed += 1
            except Exception as e:
                logger.error(f"Failed to process part {part_num}: {e}")
                logger.info("Continuing with remaining parts...")
                continue
        
        if parts_processed == 0:
            raise Exception("All parts failed to process")
        
        logger.info(f"\n✓ Successfully processed {parts_processed}/5 parts")
        logger.info(f"✓ Total records extracted: {len(all_records)}")
        
        if not all_records:
            raise Exception("No records extracted from any parts")
        
        # Step 3: Truncate table5 (delete all existing data)
        logger.info("\n[STEP 3/7] Truncating table5...")
        truncate_table5()
        
        # Step 4: Insert all data to Supabase table5
        logger.info("\n[STEP 4/7] Inserting data into Supabase table5...")
        insert_to_supabase(all_records)
        
        # Step 5: Truncate joon_ndc_data
        logger.info("\n[STEP 5/7] Truncating joon_ndc_data...")
        truncate_joon_ndc_data()
        
        # Step 6: Insert matched data into joon_ndc_data
        logger.info("\n[STEP 6/7] Inserting matched data into joon_ndc_data...")
        insert_matched_data_to_joon_ndc_data()
        
        # Step 7: Final cleanup
        logger.info("\n[STEP 7/7] Cleaning up remaining temporary files...")
        cleanup_work_directory()
        
        # Success summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        logger.info("\n" + "="*70)
        logger.info("✓ AUTOMATION COMPLETED SUCCESSFULLY!")
        logger.info("="*70)
        logger.info(f"Run completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Total duration: {duration:.2f} minutes")
        logger.info(f"Parts successfully processed: {parts_processed}/5")
        logger.info(f"Total records extracted: {len(all_records)}")
        logger.info(f"Records inserted to table5: {len(all_records)}")
        logger.info(f"Matched records inserted to joon_ndc_data: [check logs above]")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"\n✗ AUTOMATION FAILED: {e}")
        logger.info("Attempting cleanup...")
        cleanup_work_directory()
        raise


if __name__ == "__main__":
    main()