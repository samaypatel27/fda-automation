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

# Variables to change for each zip file
DAILYMED_ZIP_URL = "https://dailymed-data.nlm.nih.gov/public-release-files/dm_spl_release_human_rx_part5.zip"
DAILYMED_FILE_NAME = "dm_spl_release_human_rx_part5"

# Working directory name - everything happens inside this folder
WORKING_DIR = "ndc_extraction_temp"

# Define namespaces for XML parsing
namespaces = {
    'v3': 'urn:hl7-org:v3'
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ndc_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ========================================
# STEP 1: DOWNLOAD THE DAILYMED ZIP FILE
# ========================================

def download_dailymed_zip(url, working_dir):
    """
    Download the DailyMed ZIP file from the given URL into the working directory.
    
    Args:
        url: URL of the ZIP file to download
        working_dir: Working directory to save the file
    
    Returns:
        Path object pointing to the downloaded file
    
    Progress: Downloads the main ZIP file (~2-3 GB)
    """
    logger.info(f"Starting download from {url}")
    output_file = Path(working_dir) / f"{DAILYMED_FILE_NAME}.zip"
    
    # Check if file already exists
    if output_file.exists():
        logger.info(f"File {output_file.name} already exists. Skipping download.")
        return output_file
    
    try:
        # Stream download with progress bar
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_file, 'wb') as f, tqdm(
            desc=output_file.name,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as progress_bar:
            for chunk in response.iter_content(chunk_size=8192):
                size = f.write(chunk)
                progress_bar.update(size)
        
        logger.info(f"Download complete: {output_file}")
        return output_file
    
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise


# ========================================
# STEP 2: EXTRACT MAIN ZIP FILE
# ========================================

def extract_main_zip(zip_path):
    """
    Extract the main DailyMed ZIP file.
    
    Args:
        zip_path: Path to the ZIP file
    
    Returns:
        Path object pointing to the extracted directory
    
    Progress: Extracts main ZIP → creates dm_spl_release_human_rx_part1/ folder inside working dir
    """
    logger.info(f"Extracting main ZIP file: {zip_path}")
    # Extract to same directory as the ZIP file
    extract_dir = zip_path.parent / DAILYMED_FILE_NAME
    
    # Check if already extracted
    if extract_dir.exists():
        logger.info(f"Directory {extract_dir.name} already exists. Skipping extraction.")
        return extract_dir
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        logger.info(f"Main ZIP extracted to: {extract_dir}")
        return extract_dir
    
    except Exception as e:
        logger.error(f"Error extracting main ZIP: {e}")
        raise


# ========================================
# STEP 3: CREATE XML_FILES DIRECTORY
# ========================================

def create_xml_directory(base_dir, xml_dir_name="xml_files"):
    """
    Create the xml_files directory where all XML files will be stored.
    
    Args:
        base_dir: Base directory (dm_spl_release_human_rx_part1/)
        xml_dir_name: Name of the XML directory to create
    
    Returns:
        Path object pointing to the xml_files directory
    
    Progress: Creates xml_files/ directory at the base level
    """
    xml_dir = Path(base_dir) / xml_dir_name
    
    if xml_dir.exists():
        logger.info(f"Directory {xml_dir} already exists.")
    else:
        xml_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {xml_dir}")
    
    return xml_dir


# ========================================
# STEP 4: EXTRACT NESTED ZIP FILES
# ========================================

def extract_nested_zips_and_collect_xmls(prescription_dir, xml_output_dir):
    """
    Extract all ZIP files inside prescription/ directory and move XML files to xml_files/.
    
    Args:
        prescription_dir: Path to the prescription/ directory
        xml_output_dir: Path to the xml_files/ directory
    
    Progress: 
        - Finds all ZIP files in prescription/
        - Extracts each ZIP (contains XML files)
        - Moves XML files to xml_files/
        - Cleans up extracted folders
    """
    prescription_path = Path(prescription_dir)
    xml_output_path = Path(xml_output_dir)
    
    if not prescription_path.exists():
        logger.error(f"Prescription directory not found: {prescription_path}")
        raise FileNotFoundError(f"Directory not found: {prescription_path}")
    
    # Find all ZIP files in prescription/
    zip_files = list(prescription_path.glob("*.zip"))
    logger.info(f"Found {len(zip_files)} ZIP files in {prescription_path}")
    
    if len(zip_files) == 0:
        logger.warning("No ZIP files found in prescription/ directory")
        return
    
    total_xmls = 0
    
    # Process each ZIP file
    for i, zip_file in enumerate(zip_files, 1):
        try:
            logger.info(f"[{i}/{len(zip_files)}] Processing: {zip_file.name}")
            
            # Create temporary extraction directory
            temp_extract_dir = prescription_path / f"temp_extract_{zip_file.stem}"
            
            # Extract the ZIP file
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
            
            # Find and move all XML files
            xml_files = list(temp_extract_dir.rglob("*.xml"))
            
            for xml_file in xml_files:
                dest_file = xml_output_path / xml_file.name
                # Handle duplicate filenames
                counter = 1
                while dest_file.exists():
                    dest_file = xml_output_path / f"{xml_file.stem}_{counter}.xml"
                    counter += 1
                
                shutil.move(str(xml_file), str(dest_file))
                total_xmls += 1
            
            # Clean up temporary extraction directory
            shutil.rmtree(temp_extract_dir)
            
            if i % 10 == 0:
                logger.info(f"  Progress: {i}/{len(zip_files)} ZIPs processed, {total_xmls} XMLs collected")
        
        except Exception as e:
            logger.error(f"Error processing {zip_file.name}: {e}")
            continue
    
    logger.info(f"Extraction complete: {total_xmls} XML files moved to {xml_output_path}")


# ========================================
# STEP 5: PARSE XML FILES (EXISTING LOGIC)
# ========================================

def establishments2(label_xml):
    """
    Extract establishment data from an XML label.
    
    This is the existing function that parses XML structure to find:
    - Establishment names
    - DUNS numbers
    - Activity types (MANUFACTURE, etc.)
    - NDC codes
    
    Returns: List of [count, name, duns, activity, activity_code, ndc]
    """
    count = 0
    estab_list = []
    if label_xml.xpath("//v3:author/v3:assignedEntity/v3:representedOrganization/v3:assignedEntity/v3:assignedOrganization/v3:assignedEntity",namespaces=namespaces) != []:
        for estab in label_xml.xpath("//v3:author/v3:assignedEntity/v3:representedOrganization/v3:assignedEntity/v3:assignedOrganization/v3:assignedEntity",namespaces=namespaces):
            count += 1
            try:
                est = estab.xpath(".//v3:name",namespaces=namespaces)[0].text # establishment name
            except IndexError:
                est = "n/a"
            try:
                est_dun = estab.xpath(".//v3:id/@extension",namespaces=namespaces)[0] # establishment dun
            except IndexError:
                est_dun = "n/a"
            if estab.xpath(".//v3:performance/v3:actDefinition",namespaces=namespaces) != []:
                for perf in estab.xpath(".//v3:performance/v3:actDefinition",namespaces=namespaces): # opr name
                    try:
                        act = perf.xpath("./v3:code/@displayName",namespaces=namespaces)[0]
                    except IndexError:
                        act = "n/a"
                    try:
                        act_code = perf.xpath("./v3:code/@code",namespaces=namespaces)[0]
                    except IndexError:
                        act_code = "n/a"
                    try:
                        ndc = perf.xpath("./v3:product/v3:manufacturedProduct/v3:manufacturedMaterialKind/v3:code/@code",namespaces=namespaces)
                    except IndexError:
                        ndc = "n/a"

                    if ndc != "n/a" and len(ndc)>0: # if ndc is presented as in label ID = 11
                        for e in ndc:
                            estab_list.append([count, est, est_dun, act, act_code, e])
                    else:
                        ndc = "n/a"
                        estab_list.append([count, est, est_dun, act, act_code, ndc])
            else:
                act = "n/a"
                act_code = "n/a"
                ndc = "n/a"
                estab_list.append([count, est, est_dun, act, act_code, ndc])
    else:
        est = "n/a"
        est_dun = "n/a"
        act = "n/a"
        act_code = "n/a"
        ndc = "n/a"
        estab_list.append([count, est, est_dun, act, act_code, ndc])
    return estab_list


# ========================================
# STEP 6: TRAVERSE XML FILES AND EXTRACT DATA
# ========================================

def traverse_xmls_and_extract_data(xml_dir):
    """
    Traverse all XML files in xml_files/ directory and extract NDC-DUNS mappings.
    
    Args:
        xml_dir: Path to the xml_files directory
    
    Returns:
        List of NDC-DUNS mappings [{ndc, duns, ndc_digits}, ...]
    
    Progress:
        - Reads all XML files
        - Parses each with establishments2()
        - Filters for MANUFACTURE activities only
        - Extracts NDC, DUNS, and NDC_DIGITS
        - Returns list of all mappings (including duplicates)
    """
    xml_path = Path(xml_dir)
    
    if not xml_path.exists():
        logger.error(f"XML directory not found: {xml_path}")
        raise FileNotFoundError(f"Directory not found: {xml_path}")
    
    xml_files = list(xml_path.glob("*.xml"))
    logger.info(f"Found {len(xml_files)} XML files to process in {xml_path}")
    
    if len(xml_files) == 0:
        logger.warning("No XML files found to process")
        return []
    
    # List to store ALL NDC-DUNS mappings (no deduplication)
    ndc_duns_list = []
    
    # Create parser with HUGE option to handle deeply nested XML
    parser = etree.XMLParser(huge_tree=True)
    
    stats = {
        'total_rows': 0,
        'manufacture_records': 0,
        'has_both': 0,
        'has_ndc_only': 0,
        'has_duns_only': 0,
        'has_neither': 0,
        'total_mappings': 0
    }
    
    # Process each XML file
    for i, xml_file in enumerate(xml_files, 1):
        try:
            tree = etree.parse(str(xml_file), parser)
            estab_data = establishments2(tree)
            
            stats['total_rows'] += len(estab_data)
            
            # Process the data: extract NDC and DUNS pairs
            for row in estab_data:
                # row format: [count, est, est_dun, act, act_code, ndc]
                activity = row[3]  # Activity type (MANUFACTURE, etc.)
                ndc = row[5]  # NDC code
                duns = row[2]  # DUNS number (est_dun)
                
                # ONLY process MANUFACTURE activities
                if activity == "MANUFACTURE" or activity == "manufacture":
                    stats['manufacture_records'] += 1
                    
                    # Convert "n/a" to None for database null
                    ndc_value = None if ndc == "n/a" else ndc
                    duns_value = None if duns == "n/a" else duns
                    
                    # Track statistics
                    if ndc_value and duns_value:
                        stats['has_both'] += 1
                    elif ndc_value and not duns_value:
                        stats['has_ndc_only'] += 1
                    elif duns_value and not ndc_value:
                        stats['has_duns_only'] += 1
                    else:
                        stats['has_neither'] += 1
                    
                    # Skip records where BOTH are None
                    if not ndc_value and not duns_value:
                        continue
                    
                    # Calculate ndc_digits (remove dashes)
                    ndc_digits = ndc_value.replace("-", "") if ndc_value else None
                    
                    # Add to list (no deduplication)
                    ndc_duns_list.append({
                        "ndc": ndc_value,
                        "duns": duns_value,
                        "ndc_digits": ndc_digits
                    })
            
            # Progress update every 100 files
            if i % 100 == 0:
                logger.info(f"  Progress: {i}/{len(xml_files)} files processed, {len(ndc_duns_list)} total mappings")
        
        except Exception as e:
            logger.error(f"Error processing {xml_file.name}: {e}")
            continue
    
    stats['total_mappings'] = len(ndc_duns_list)
    
    # Print statistics
    logger.info(f"\n{'='*50}")
    logger.info(f"EXTRACTION STATISTICS")
    logger.info(f"{'='*50}")
    logger.info(f"Total rows from establishments2(): {stats['total_rows']}")
    logger.info(f"MANUFACTURE records found: {stats['manufacture_records']}")
    logger.info(f"  - Has both NDC and DUNS: {stats['has_both']}")
    logger.info(f"  - Has NDC only (DUNS is null): {stats['has_ndc_only']}")
    logger.info(f"  - Has DUNS only (NDC is null): {stats['has_duns_only']}")
    logger.info(f"  - Has neither (skipped): {stats['has_neither']}")
    logger.info(f"Total NDC-DUNS mappings: {stats['total_mappings']}")
    logger.info(f"{'='*50}\n")
    
    return ndc_duns_list


# ========================================
# STEP 7: INSERT DATA INTO SUPABASE
# ========================================

def insert_to_supabase(data_list):
    """
    Insert NDC-DUNS mappings into Supabase table5.
    
    Args:
        data_list: List of NDC-DUNS mappings
    
    Progress:
        - Inserts in batches of 1000
        - Falls back to one-by-one insertion on batch failure
        - Logs progress for each batch
    """
    if not data_list:
        logger.warning("No data to insert into Supabase")
        return
    
    logger.info(f"Inserting {len(data_list)} NDC-DUNS mappings into Supabase table5")
    
    batch_size = 1000
    total_inserted = 0
    total_batches = (len(data_list) + batch_size - 1) // batch_size
    
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        try:
            response = supabase.table("table5").insert(batch).execute()
            total_inserted += len(batch)
            logger.info(f"Batch {batch_num}/{total_batches}: Inserted {total_inserted}/{len(data_list)} records")
        except Exception as e:
            logger.error(f"Error inserting batch {batch_num}: {e}")
            logger.info(f"  Falling back to one-by-one insertion...")
            
            for record in batch:
                try:
                    supabase.table("table5").insert(record).execute()
                    total_inserted += 1
                except Exception as record_error:
                    logger.error(f"Failed to insert NDC {record['ndc']}: {record_error}")
    
    logger.info(f"Insertion complete: {total_inserted}/{len(data_list)} records inserted")


# ========================================
# STEP 8: CLEANUP WORKING DIRECTORY
# ========================================

def cleanup_working_directory(working_dir):
    """
    Delete the entire working directory and all its contents.
    
    Args:
        working_dir: Path to the working directory
    
    Progress: Removes all downloaded and extracted files to free disk space
    """
    working_path = Path(working_dir)
    
    if working_path.exists():
        logger.info(f"Cleaning up working directory: {working_dir}")
        shutil.rmtree(working_path)
        logger.info(f"Deleted working directory: {working_dir}")
    else:
        logger.info(f"Working directory {working_dir} does not exist, nothing to clean up")


# ========================================
# MAIN ORCHESTRATION
# ========================================

def main():
    """
    Main orchestration function that runs the entire pipeline.
    
    Pipeline Steps:
    0. Create temporary working directory
    1. Download DailyMed ZIP file
    2. Extract main ZIP file
    3. Create xml_files directory
    4. Extract nested ZIPs and collect XML files
    5. Traverse XMLs and extract NDC-DUNS data
    6. Insert data into Supabase
    7. Cleanup working directory (delete everything)
    """
    logger.info("="*60)
    logger.info("NDC-DUNS EXTRACTION PIPELINE STARTED")
    logger.info("="*60)
    
    # Create working directory
    working_path = Path(WORKING_DIR)
    working_path.mkdir(exist_ok=True)
    logger.info(f"\n[STEP 0/7] Created working directory: {WORKING_DIR}")
    
    try:
        # Step 1: Download the DailyMed ZIP file
        logger.info("\n[STEP 1/7] Downloading DailyMed ZIP file...")
        zip_file = download_dailymed_zip(DAILYMED_ZIP_URL, working_path)
        
        # Step 2: Extract the main ZIP file
        logger.info("\n[STEP 2/7] Extracting main ZIP file...")
        extracted_dir = extract_main_zip(zip_file)
        
        # Step 3: Create xml_files directory
        logger.info("\n[STEP 3/7] Creating xml_files directory...")
        xml_dir = create_xml_directory(extracted_dir)
        
        # Step 4: Extract nested ZIPs and collect XMLs
        logger.info("\n[STEP 4/7] Extracting nested ZIPs and collecting XML files...")
        prescription_dir = extracted_dir / "prescription"
        extract_nested_zips_and_collect_xmls(prescription_dir, xml_dir)
        
        # Step 5: Traverse XMLs and extract data
        logger.info("\n[STEP 5/7] Traversing XML files and extracting data...")
        ndc_duns_data = traverse_xmls_and_extract_data(xml_dir)
        
        # Step 6: Insert data into Supabase
        logger.info("\n[STEP 6/7] Inserting data into Supabase...")
        if ndc_duns_data:
            insert_to_supabase(ndc_duns_data)
        else:
            logger.warning("No data to insert!")
        
        # Step 7: Cleanup working directory
        logger.info("\n[STEP 7/7] Cleaning up working directory...")
        cleanup_working_directory(working_path)
        
        logger.info("\n" + "="*60)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("="*60)
    
    except Exception as e:
        logger.error(f"\n{'='*60}")
        logger.error(f"PIPELINE FAILED: {e}")
        logger.error(f"{'='*60}")
        
        # Still try to cleanup on failure
        logger.info("\nAttempting cleanup despite failure...")
        try:
            cleanup_working_directory(working_path)
        except:
            logger.warning(f"Could not cleanup working directory: {working_path}")
        
        raise


if __name__ == "__main__":
    main()