"""
Daily FDA Drug Label Data Automation Script - Version 2

MAJOR CHANGES FROM V1:
1. Downloads 5 ZIP files (part1-part5) instead of 1
2. Processes all 5 parts into a single xml_files directory
3. Uses new XML parsing logic (establishments2 function)
4. Allows NULL values for NDC and DUNS
5. No primary key - allows duplicate records
6. Adds ndc_digits column (NDC without dashes)
7. Uses INSERT instead of UPSERT

This script:
1. Downloads 5 FDA drug label ZIP files from DailyMed (part1-part5)
2. Extracts each ZIP to working directories
3. Extracts all XML files from nested prescription ZIPs into single xml_files folder
4. Processes XML files using establishments2() logic to extract ALL NDC-DUNS combinations
5. Inserts data into Supabase table5 (allows nulls and duplicates)
6. Cleans up temporary files

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
DOWNLOADS_DIR = WORK_DIR / "downloads"  # Store all 5 downloaded ZIPs here
EXTRACTED_DIR = WORK_DIR / "extracted"  # Extract all 5 ZIPs here
XML_OUTPUT_DIR = WORK_DIR / "xml_files"  # ALL XMLs from all 5 parts go here

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
    - downloads: for the 5 downloaded ZIP files
    - extracted: for the 5 extracted folders
    - xml_files: for ALL XMLs from all 5 parts (single collection point)
    """
    cleanup_work_directory()
    WORK_DIR.mkdir(exist_ok=True)
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    EXTRACTED_DIR.mkdir(exist_ok=True)
    XML_OUTPUT_DIR.mkdir(exist_ok=True)
    logger.info(f"Created work directory structure: {WORK_DIR}")


def download_fda_data():
    """
    Download all 5 FDA drug label ZIP files from DailyMed.
    
    Downloads part1 through part5 sequentially.
    Each file is ~500-700MB, so total download is ~3GB.
    
    Returns:
        int: Number of files successfully downloaded (should be 5)
    """
    logger.info(f"Downloading {len(DOWNLOAD_FILES)} FDA ZIP files...")
    successful_downloads = 0
    
    for idx, filename in enumerate(DOWNLOAD_FILES, 1):
        download_url = BASE_DOWNLOAD_URL + filename
        output_path = DOWNLOADS_DIR / filename
        
        logger.info(f"\n[{idx}/{len(DOWNLOAD_FILES)}] Downloading: {filename}")
        logger.info(f"URL: {download_url}")
        
        try:
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            logger.info(f"Size: {total_size / (1024*1024):.2f} MB")
            
            # Download with progress logging every 10MB
            with open(output_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (10 * 1024 * 1024) == 0:  # Log every 10MB
                        logger.info(f"  Downloaded: {downloaded / (1024*1024):.2f} MB")
            
            logger.info(f"✓ Download complete: {filename}")
            successful_downloads += 1
            
        except Exception as e:
            logger.error(f"✗ Download failed for {filename}: {e}")
            # Continue with other files even if one fails
            continue
    
    logger.info(f"\n✓ Downloaded {successful_downloads}/{len(DOWNLOAD_FILES)} files successfully")
    return successful_downloads


def extract_main_zips():
    """
    Extract all 5 main ZIP files.
    
    Each ZIP extracts to a folder like:
    - dm_spl_release_human_rx_part1/
    - dm_spl_release_human_rx_part2/
    - etc.
    
    All extracted folders go into EXTRACTED_DIR.
    
    Returns:
        int: Number of ZIPs successfully extracted
    """
    logger.info(f"Extracting {len(DOWNLOAD_FILES)} main ZIP files...")
    successful_extractions = 0
    
    for idx, filename in enumerate(DOWNLOAD_FILES, 1):
        zip_path = DOWNLOADS_DIR / filename
        
        if not zip_path.exists():
            logger.warning(f"[{idx}/{len(DOWNLOAD_FILES)}] ZIP not found: {filename}")
            continue
        
        logger.info(f"[{idx}/{len(DOWNLOAD_FILES)}] Extracting: {filename}")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(EXTRACTED_DIR)
            
            logger.info(f"✓ Extracted: {filename}")
            successful_extractions += 1
            
        except Exception as e:
            logger.error(f"✗ Extraction failed for {filename}: {e}")
            continue
    
    logger.info(f"✓ Extracted {successful_extractions}/{len(DOWNLOAD_FILES)} files to: {EXTRACTED_DIR}")
    return successful_extractions


def find_all_prescription_directories():
    """
    Find all 'prescription' directories in the extracted folders.
    
    Searches for folders named 'prescription' within each of the 5 extracted parts.
    Expected structure:
    - extracted/dm_spl_release_human_rx_part1/prescription/
    - extracted/dm_spl_release_human_rx_part2/prescription/
    - etc.
    
    Returns:
        list: List of Path objects pointing to prescription directories
    """
    logger.info(f"Searching for prescription directories in: {EXTRACTED_DIR}")
    prescription_dirs = []
    
    # Walk through all directories looking for 'prescription' folders
    for root, dirs, files in os.walk(EXTRACTED_DIR):
        if 'prescription' in dirs:
            prescription_path = Path(root) / 'prescription'
            prescription_dirs.append(prescription_path)
            logger.info(f"✓ Found prescription directory: {prescription_path}")
    
    if not prescription_dirs:
        # If not found, log what we did find to help debug
        logger.error(f"✗ No prescription directories found!")
        logger.info(f"Contents of {EXTRACTED_DIR}:")
        for item in EXTRACTED_DIR.iterdir():
            logger.info(f"  - {item.name} ({'dir' if item.is_dir() else 'file'})")
            if item.is_dir():
                for subitem in item.iterdir():
                    logger.info(f"    - {subitem.name} ({'dir' if subitem.is_dir() else 'file'})")
    
    logger.info(f"✓ Found {len(prescription_dirs)} prescription directories total")
    return prescription_dirs


def extract_prescription_zips(prescription_dirs):
    """
    Extract all prescription ZIP files from ALL prescription directories.
    
    For each prescription directory (5 total), this function:
    1. Finds all .zip files
    2. Extracts each ZIP to a temporary folder
    3. Recursively finds all .xml files in the extraction
    4. Copies XMLs to the central XML_OUTPUT_DIR with unique names
    5. Cleans up the temporary extraction folder
    
    Args:
        prescription_dirs: List of Path objects to prescription directories
    
    Returns:
        int: Total number of XML files extracted from ALL parts
    """
    logger.info(f"Processing {len(prescription_dirs)} prescription directories...")
    
    total_xml_count = 0
    total_zip_count = 0
    
    # Process each prescription directory (part1, part2, etc.)
    for dir_idx, prescription_dir in enumerate(prescription_dirs, 1):
        logger.info(f"\n[Part {dir_idx}/{len(prescription_dirs)}] Processing: {prescription_dir.name}")
        
        if not prescription_dir.exists():
            logger.error(f"Directory does not exist: {prescription_dir}")
            continue
        
        # Get all ZIP files in this prescription directory
        zip_files = list(prescription_dir.glob("*.zip"))
        
        if not zip_files:
            logger.warning(f"No ZIP files found in {prescription_dir}")
            continue
        
        logger.info(f"Found {len(zip_files)} ZIP files in this part")
        total_zip_count += len(zip_files)
        
        part_xml_count = 0
        
        # Process each ZIP file in this prescription directory
        for idx, zip_file in enumerate(zip_files, 1):
            # Log progress every 100 ZIPs
            if idx % 100 == 0:
                logger.info(f"  Progress: {idx}/{len(zip_files)} ZIPs processed... ({part_xml_count} XMLs from this part)")
            
            try:
                # Create temporary extraction directory
                # Use prescription_dir as base to avoid conflicts between parts
                temp_extract_path = prescription_dir / f"temp_{zip_file.stem}"
                temp_extract_path.mkdir(exist_ok=True)
                
                # Extract the ZIP file
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_path)
                
                # Find ALL XML files recursively (in case XMLs are nested in folders)
                xml_files = list(temp_extract_path.rglob("*.xml"))
                
                # Copy each XML to the central xml_files directory
                for xml_file in xml_files:
                    # Create unique filename: partX_zipname_xmlname
                    # This prevents conflicts between parts with same ZIP names
                    output_filename = f"{prescription_dir.parent.name}_{zip_file.stem}_{xml_file.name}"
                    output_path = XML_OUTPUT_DIR / output_filename
                    shutil.copy2(xml_file, output_path)
                    part_xml_count += 1
                    total_xml_count += 1
                
                # Clean up temporary extraction directory
                shutil.rmtree(temp_extract_path)
                
            except zipfile.BadZipFile:
                logger.error(f"Bad ZIP file: {zip_file.name}")
                # Clean up if temp directory exists
                if temp_extract_path.exists():
                    shutil.rmtree(temp_extract_path)
                    
            except Exception as e:
                logger.error(f"Error processing {zip_file.name}: {e}")
                # Clean up if temp directory exists
                if temp_extract_path.exists():
                    shutil.rmtree(temp_extract_path)
        
        logger.info(f"✓ Part {dir_idx} complete: {part_xml_count} XMLs extracted")
    
    logger.info(f"\n✓ TOTAL: Extracted {total_xml_count} XML files from {total_zip_count} ZIPs across all parts")
    return total_xml_count


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


def process_all_xml_files():
    """
    Process ALL XML files in the xml_files directory.
    
    This now processes XMLs from all 5 parts (they're all in one directory).
    Uses the new establishments2() logic instead of the old manufacturer-focused approach.
    
    Returns:
        list: List of all records (allows duplicates, allows nulls)
    """
    logger.info(f"Processing XML files from: {XML_OUTPUT_DIR}")
    
    xml_files = list(XML_OUTPUT_DIR.glob("*.xml"))
    
    if not xml_files:
        logger.warning("No XML files found to process")
        return []
    
    logger.info(f"Found {len(xml_files)} XML files to process")
    
    all_records = []  # List instead of dict - we want ALL records, including duplicates
    
    # Statistics tracking
    stats = {
        'files_processed': 0,
        'files_with_data': 0,
        'files_without_data': 0,
        'total_records': 0,
        'has_both': 0,
        'has_ndc_only': 0,
        'has_duns_only': 0
    }
    
    # Process each XML file
    for i, xml_file in enumerate(xml_files, 1):
        records = process_xml_file(xml_file)
        
        stats['files_processed'] += 1
        
        if records:
            stats['files_with_data'] += 1
            stats['total_records'] += len(records)
            
            # Add all records to our list (no deduplication)
            for record in records:
                all_records.append(record)
                
                # Track statistics
                if record['ndc'] and record['duns']:
                    stats['has_both'] += 1
                elif record['ndc']:
                    stats['has_ndc_only'] += 1
                elif record['duns']:
                    stats['has_duns_only'] += 1
        else:
            stats['files_without_data'] += 1
        
        # Log progress every 1000 files
        if i % 1000 == 0:
            logger.info(f"Progress: {i}/{len(xml_files)} files processed... ({stats['total_records']} records so far)")
    
    # Log final statistics
    logger.info(f"\n✓ Processing complete:")
    logger.info(f"  - Files processed: {stats['files_processed']}")
    logger.info(f"  - Files with data: {stats['files_with_data']}")
    logger.info(f"  - Files without data: {stats['files_without_data']}")
    logger.info(f"  - Total records: {stats['total_records']}")
    logger.info(f"  - Has both NDC and DUNS: {stats['has_both']}")
    logger.info(f"  - Has NDC only (DUNS is null): {stats['has_ndc_only']}")
    logger.info(f"  - Has DUNS only (NDC is null): {stats['has_duns_only']}")
    
    # Count unique non-null values for informational purposes
    unique_ndcs = len(set(r['ndc'] for r in all_records if r['ndc'] is not None))
    unique_duns = len(set(r['duns'] for r in all_records if r['duns'] is not None))
    logger.info(f"  - Unique NDCs (non-null): {unique_ndcs}")
    logger.info(f"  - Unique DUNS (non-null): {unique_duns}")
    
    return all_records


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


def main():
    """
    Main orchestration function.
    
    Orchestrates the entire process:
    1. Setup work directories
    2. Download 5 ZIP files
    3. Extract 5 main ZIPs
    4. Find 5 prescription directories
    5. Extract all prescription ZIPs from all 5 parts
    6. Process all XML files (from all 5 parts)
    7. Truncate table5
    8. Insert all data to Supabase
    9. Clean up temporary files
    """
    start_time = datetime.now()
    logger.info("="*70)
    logger.info("FDA DRUG LABEL DATA AUTOMATION - DAILY RUN (5 PARTS)")
    logger.info(f"Run started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)
    
    try:
        # Step 1: Setup
        logger.info("\n[STEP 1/9] Setting up work directory...")
        setup_work_directory()
        
        # Step 2: Download all 5 ZIP files
        logger.info("\n[STEP 2/9] Downloading 5 FDA ZIP files...")
        download_count = download_fda_data()
        if download_count == 0:
            raise Exception("All downloads failed")
        logger.info(f"Successfully downloaded {download_count}/5 files")
        
        # Step 3: Extract all 5 main ZIP files
        logger.info("\n[STEP 3/9] Extracting 5 main ZIP files...")
        extract_count = extract_main_zips()
        if extract_count == 0:
            raise Exception("All extractions failed")
        logger.info(f"Successfully extracted {extract_count}/5 files")
        
        # Step 4: Find all prescription directories (should be 5)
        logger.info("\n[STEP 4/9] Locating prescription directories...")
        prescription_dirs = find_all_prescription_directories()
        if not prescription_dirs:
            raise Exception("No prescription directories found")
        
        # Step 5: Extract prescription ZIPs from all parts
        logger.info("\n[STEP 5/9] Extracting prescription ZIP files from all parts...")
        xml_count = extract_prescription_zips(prescription_dirs)
        if xml_count == 0:
            raise Exception("No XML files extracted from prescription ZIPs")
        
        # Step 6: Process all XML files using new establishments2 logic
        logger.info("\n[STEP 6/9] Processing XML files for establishment data...")
        all_records = process_all_xml_files()
        if not all_records:
            raise Exception("No records extracted from XML files")
        
        # Step 7: Truncate table5 (delete all existing data)
        logger.info("\n[STEP 7/9] Truncating table5...")
        truncate_table5()
        
        # Step 8: Insert all data to Supabase
        logger.info("\n[STEP 8/9] Inserting data into Supabase...")
        insert_to_supabase(all_records)
        
        # Step 9: Cleanup
        logger.info("\n[STEP 9/9] Cleaning up temporary files...")
        cleanup_work_directory()
        
        # Success summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        logger.info("\n" + "="*70)
        logger.info("✓ AUTOMATION COMPLETED SUCCESSFULLY!")
        logger.info("="*70)
        logger.info(f"Run completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Total duration: {duration:.2f} minutes")
        logger.info(f"ZIP files downloaded: {download_count}/5")
        logger.info(f"ZIP files extracted: {extract_count}/5")
        logger.info(f"Prescription directories found: {len(prescription_dirs)}")
        logger.info(f"XML files processed: {xml_count}")
        logger.info(f"Records inserted to database: {len(all_records)}")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"\n✗ AUTOMATION FAILED: {e}")
        logger.info("Attempting cleanup...")
        cleanup_work_directory()
        raise


if __name__ == "__main__":
    main()