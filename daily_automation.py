"""
Daily FDA Drug Label Data Automation Script

This script:
1. Downloads the FDA drug label ZIP file from DailyMed
2. Extracts it to a working directory
3. Extracts all XML files from nested ZIPs (using extract_xml.py logic)
4. Processes XML files to extract NDC-DUNS mappings (using app4.py logic)
5. Inserts data into Supabase table5
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

# Load environment variables
load_dotenv()

# Configuration
DOWNLOAD_URL = "https://dailymed-data.nlm.nih.gov/public-release-files/dm_spl_release_human_rx_part1.zip"
WORK_DIR = Path("temp_work")
DOWNLOADED_ZIP = WORK_DIR / "downloaded.zip"
EXTRACTED_DIR = WORK_DIR / "extracted"
XML_OUTPUT_DIR = WORK_DIR / "xml_files"

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# XML namespaces
namespaces = {'v3': 'urn:hl7-org:v3'}


def cleanup_work_directory():
    """Remove the temporary work directory if it exists."""
    if WORK_DIR.exists():
        logger.info(f"Cleaning up work directory: {WORK_DIR}")
        shutil.rmtree(WORK_DIR)


def setup_work_directory():
    """Create fresh work directory structure."""
    cleanup_work_directory()
    WORK_DIR.mkdir(exist_ok=True)
    EXTRACTED_DIR.mkdir(exist_ok=True)
    XML_OUTPUT_DIR.mkdir(exist_ok=True)
    logger.info(f"Created work directory: {WORK_DIR}")


def download_fda_data():
    """Download the FDA drug label ZIP file."""
    logger.info(f"Downloading FDA data from: {DOWNLOAD_URL}")
    
    try:
        response = requests.get(DOWNLOAD_URL, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        logger.info(f"Download size: {total_size / (1024*1024):.2f} MB")
        
        with open(DOWNLOADED_ZIP, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded % (10 * 1024 * 1024) == 0:  # Log every 10MB
                    logger.info(f"Downloaded: {downloaded / (1024*1024):.2f} MB")
        
        logger.info(f"✓ Download complete: {DOWNLOADED_ZIP}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Download failed: {e}")
        return False


def extract_main_zip():
    """Extract the main downloaded ZIP file."""
    logger.info(f"Extracting main ZIP file: {DOWNLOADED_ZIP}")
    
    try:
        with zipfile.ZipFile(DOWNLOADED_ZIP, 'r') as zip_ref:
            zip_ref.extractall(EXTRACTED_DIR)
        
        logger.info(f"✓ Main ZIP extracted to: {EXTRACTED_DIR}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Extraction failed: {e}")
        return False


def find_prescription_directory():
    """
    Find the prescription directory dynamically.
    Searches for a folder named 'prescription' anywhere in the extracted directory.
    """
    logger.info(f"Searching for prescription directory in: {EXTRACTED_DIR}")
    
    # Search for any directory named 'prescription'
    for root, dirs, files in os.walk(EXTRACTED_DIR):
        if 'prescription' in dirs:
            prescription_path = Path(root) / 'prescription'
            logger.info(f"✓ Found prescription directory: {prescription_path}")
            return prescription_path
    
    # If not found, log what we did find
    logger.error(f"✗ Prescription directory not found!")
    logger.info(f"Contents of {EXTRACTED_DIR}:")
    for item in EXTRACTED_DIR.iterdir():
        logger.info(f"  - {item.name} ({'dir' if item.is_dir() else 'file'})")
        if item.is_dir():
            for subitem in item.iterdir():
                logger.info(f"    - {subitem.name} ({'dir' if subitem.is_dir() else 'file'})")
    
    return None


def extract_prescription_zips(prescription_dir):
    """
    Extract all ZIP files from the prescription directory.
    This is the logic from extract_xml.py.
    """
    logger.info(f"Extracting prescription ZIP files from: {prescription_dir}")
    
    if not prescription_dir or not prescription_dir.exists():
        logger.error(f"Prescription directory not found or invalid: {prescription_dir}")
        return 0
    
    zip_files = list(prescription_dir.glob("*.zip"))
    total_zips = len(zip_files)
    
    if total_zips == 0:
        logger.warning("No ZIP files found in prescription directory")
        logger.info(f"Contents of {prescription_dir}:")
        for item in prescription_dir.iterdir():
            logger.info(f"  - {item.name}")
        return 0
    
    logger.info(f"Found {total_zips} prescription ZIP files to process")
    
    xml_count = 0
    
    for idx, zip_file in enumerate(zip_files, 1):
        if idx % 100 == 0:
            logger.info(f"Progress: {idx}/{total_zips} ZIPs processed... ({xml_count} XMLs collected)")
        
        try:
            # Create temporary extraction directory
            temp_extract_path = prescription_dir / f"temp_{zip_file.stem}"
            temp_extract_path.mkdir(exist_ok=True)
            
            # Extract zip file
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_path)
            
            # Find all XML files in extracted content (recursive search)
            xml_files = list(temp_extract_path.rglob("*.xml"))
            
            # Copy each XML file to output folder with unique name
            for xml_file in xml_files:
                output_filename = f"{zip_file.stem}_{xml_file.name}"
                output_path = XML_OUTPUT_DIR / output_filename
                shutil.copy2(xml_file, output_path)
                xml_count += 1
            
            # Clean up temporary extraction directory
            shutil.rmtree(temp_extract_path)
            
        except zipfile.BadZipFile:
            logger.error(f"Bad ZIP file: {zip_file.name}")
            if temp_extract_path.exists():
                shutil.rmtree(temp_extract_path)
                
        except Exception as e:
            logger.error(f"Error processing {zip_file.name}: {e}")
            if temp_extract_path.exists():
                shutil.rmtree(temp_extract_path)
    
    logger.info(f"✓ Extracted {xml_count} XML files from {total_zips} ZIPs")
    return xml_count


def is_manufacturer_activity(code_element):
    """Determine if an actDefinition represents actual manufacturing."""
    if code_element is None:
        return False
    
    display_name = code_element.get('displayName', '').upper()
    
    if 'MANUFACTURE' not in display_name:
        return False
    
    exclude_terms = ['API', 'REPACK', 'RELABEL', 'PACK', 'LABEL', 'ANALYSIS', 'COMPOUND']
    
    for term in exclude_terms:
        if term in display_name:
            return False
    
    return True


def find_all_duns_with_context(tree):
    """Find all DUNS numbers in the document with manufacturing context."""
    duns_list = []
    
    # Strategy 1: Standard author/representedOrganization path
    rep_orgs = tree.xpath("//v3:author/v3:assignedEntity/v3:representedOrganization", namespaces=namespaces)
    for org in rep_orgs:
        duns_elements = org.xpath(".//v3:id[@root='1.3.6.1.4.1.519.1']/@extension", namespaces=namespaces)
        name_elements = org.xpath("./v3:name/text()", namespaces=namespaces)
        
        if duns_elements:
            duns = duns_elements[0]
            name = name_elements[0] if name_elements else None
            
            has_manufacture = False
            act_defs = org.xpath(".//v3:performance/v3:actDefinition/v3:code", namespaces=namespaces)
            for act_def_code in act_defs:
                if is_manufacturer_activity(act_def_code):
                    has_manufacture = True
                    break
            
            duns_list.append({
                'duns': duns,
                'name': name,
                'has_manufacture': has_manufacture,
                'element': org
            })
    
    # Strategy 2: assignedOrganization elements
    assigned_orgs = tree.xpath("//v3:assignedOrganization", namespaces=namespaces)
    for org in assigned_orgs:
        duns_elements = org.xpath(".//v3:id[@root='1.3.6.1.4.1.519.1']/@extension", namespaces=namespaces)
        name_elements = org.xpath(".//v3:name/text()", namespaces=namespaces)
        
        if duns_elements:
            duns = duns_elements[0]
            name = name_elements[0] if name_elements else None
            
            if not any(d['duns'] == duns for d in duns_list):
                has_manufacture = False
                act_defs = org.xpath(".//v3:performance/v3:actDefinition/v3:code", namespaces=namespaces)
                for act_def_code in act_defs:
                    if is_manufacturer_activity(act_def_code):
                        has_manufacture = True
                        break
                
                duns_list.append({
                    'duns': duns,
                    'name': name,
                    'has_manufacture': has_manufacture,
                    'element': org
                })
    
    # Strategy 3: Catch-all for any element with DUNS root
    all_duns_elements = tree.xpath("//v3:id[@root='1.3.6.1.4.1.519.1']", namespaces=namespaces)
    for duns_elem in all_duns_elements:
        duns = duns_elem.get('extension')
        if duns:
            parent_org = duns_elem.xpath("ancestor::*[v3:name][1]", namespaces=namespaces)
            name = None
            if parent_org:
                name_elements = parent_org[0].xpath(".//v3:name/text()", namespaces=namespaces)
                name = name_elements[0] if name_elements else None
            
            if not any(d['duns'] == duns for d in duns_list):
                has_manufacture = False
                if parent_org:
                    act_defs = parent_org[0].xpath(".//v3:performance/v3:actDefinition/v3:code", namespaces=namespaces)
                    for act_def_code in act_defs:
                        if is_manufacturer_activity(act_def_code):
                            has_manufacture = True
                            break
                
                duns_list.append({
                    'duns': duns,
                    'name': name,
                    'has_manufacture': has_manufacture,
                    'element': duns_elem
                })
    
    return duns_list


def find_all_ndcs_with_context(tree):
    """Find all NDC numbers in the document with their context."""
    ndcs = []
    
    # Strategy 1: NDCs in actDefinition/product (standard manufacturing path)
    performances = tree.xpath("//v3:performance/v3:actDefinition", namespaces=namespaces)
    for perf in performances:
        code_elem = perf.xpath("./v3:code", namespaces=namespaces)
        if not code_elem or not is_manufacturer_activity(code_elem[0]):
            continue
        
        ndc_codes = perf.xpath("./v3:product/v3:manufacturedProduct/v3:manufacturedMaterialKind/v3:code[@codeSystem='2.16.840.1.113883.6.69']/@code", namespaces=namespaces)
        
        related_duns = None
        assigned_org = perf.xpath("ancestor::v3:assignedEntity/v3:assignedOrganization", namespaces=namespaces)
        if assigned_org:
            duns_elements = assigned_org[0].xpath(".//v3:id[@root='1.3.6.1.4.1.519.1']/@extension", namespaces=namespaces)
            if duns_elements:
                related_duns = duns_elements[0]
        
        for ndc in ndc_codes:
            ndcs.append({
                'ndc': ndc,
                'source_type': 'actDefinition',
                'related_duns': related_duns
            })
    
    # Strategy 2: NDCs in asEquivalentEntity sections
    equiv_entities = tree.xpath("//v3:asEquivalentEntity[@classCode='EQUIV']", namespaces=namespaces)
    for equiv in equiv_entities:
        ndc_codes = equiv.xpath(".//v3:code[@codeSystem='2.16.840.1.113883.6.69']/@code", namespaces=namespaces)
        
        related_duns = None
        manufactured_product = equiv.xpath("ancestor::v3:manufacturedProduct[1]", namespaces=namespaces)
        if manufactured_product:
            author_duns = tree.xpath("//v3:author/v3:assignedEntity/v3:representedOrganization/v3:id[@root='1.3.6.1.4.1.519.1']/@extension", namespaces=namespaces)
            if author_duns:
                related_duns = author_duns[0]
        
        for ndc in ndc_codes:
            ndcs.append({
                'ndc': ndc,
                'source_type': 'asEquivalentEntity',
                'related_duns': related_duns
            })
    
    # Strategy 3: NDCs in document body manufacturedProduct sections
    body_products = tree.xpath("//v3:component/v3:structuredBody//v3:manufacturedProduct", namespaces=namespaces)
    for product in body_products:
        ndc_codes = product.xpath("./v3:manufacturedMedicine/v3:code[@codeSystem='2.16.840.1.113883.6.69']/@code | ./v3:manufacturedProduct/v3:code[@codeSystem='2.16.840.1.113883.6.69']/@code", namespaces=namespaces)
        
        related_duns = None
        author_duns = tree.xpath("//v3:author/v3:assignedEntity/v3:representedOrganization/v3:id[@root='1.3.6.1.4.1.519.1']/@extension", namespaces=namespaces)
        if author_duns:
            related_duns = author_duns[0]
        
        for ndc in ndc_codes:
            if not any(n['ndc'] == ndc and n['source_type'] == 'documentBody' for n in ndcs):
                ndcs.append({
                    'ndc': ndc,
                    'source_type': 'documentBody',
                    'related_duns': related_duns
                })
    
    return ndcs


def process_xml_file(xml_file):
    """Process a single XML file and extract manufacturer NDC-to-DUNS mappings."""
    try:
        parser = etree.XMLParser(huge_tree=True)
        tree = etree.parse(str(xml_file), parser)
        
        all_duns = find_all_duns_with_context(tree)
        manufacturer_duns = [d for d in all_duns if d['has_manufacture']]
        
        # Fallback: use document author if no manufacturers found
        if not manufacturer_duns:
            author_orgs = tree.xpath("//v3:author/v3:assignedEntity/v3:representedOrganization", namespaces=namespaces)
            for org in author_orgs:
                duns_elements = org.xpath(".//v3:id[@root='1.3.6.1.4.1.519.1']/@extension", namespaces=namespaces)
                if duns_elements:
                    manufacturer_duns.append({
                        'duns': duns_elements[0],
                        'has_manufacture': True,
                        'element': org
                    })
        
        all_ndcs = find_all_ndcs_with_context(tree)
        
        mappings = {}
        for ndc_info in all_ndcs:
            ndc = ndc_info['ndc']
            related_duns = ndc_info['related_duns']
            
            if related_duns:
                duns_obj = next((d for d in manufacturer_duns if d['duns'] == related_duns), None)
                if duns_obj:
                    mappings[ndc] = {
                        'ndc': ndc,
                        'duns': duns_obj['duns']
                    }
            else:
                if manufacturer_duns:
                    mappings[ndc] = {
                        'ndc': ndc,
                        'duns': manufacturer_duns[0]['duns']
                    }
        
        return mappings
    
    except Exception as e:
        return {}


def process_all_xml_files():
    """Process all XML files to extract NDC-DUNS mappings."""
    logger.info(f"Processing XML files from: {XML_OUTPUT_DIR}")
    
    xml_files = list(XML_OUTPUT_DIR.glob("*.xml"))
    
    if not xml_files:
        logger.warning("No XML files found to process")
        return {}
    
    logger.info(f"Found {len(xml_files)} XML files to process")
    
    all_data = {}
    files_with_manufacturers = 0
    files_without_manufacturers = 0
    
    for i, xml_file in enumerate(xml_files, 1):
        mappings = process_xml_file(xml_file)
        
        if mappings:
            files_with_manufacturers += 1
            for ndc, data in mappings.items():
                all_data[ndc] = data
        else:
            files_without_manufacturers += 1
        
        if i % 1000 == 0:
            logger.info(f"Progress: {i}/{len(xml_files)} files processed... (Unique NDCs: {len(all_data)})")
    
    logger.info(f"✓ Processing complete:")
    logger.info(f"  - Files with manufacturers: {files_with_manufacturers}")
    logger.info(f"  - Files without manufacturers: {files_without_manufacturers}")
    logger.info(f"  - Unique NDC-DUNS mappings: {len(all_data)}")
    
    return all_data


def insert_to_supabase(data_dict):
    """Insert NDC-DUNS mappings into Supabase table5."""
    if not data_dict:
        logger.warning("No data to insert into Supabase")
        return
    
    logger.info(f"Inserting {len(data_dict)} NDC-DUNS mappings into Supabase table5")
    
    records = list(data_dict.values())
    batch_size = 1000
    total_inserted = 0
    total_batches = (len(records) + batch_size - 1) // batch_size
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        try:
            response = supabase.table("table5").upsert(batch).execute()
            total_inserted += len(batch)
            logger.info(f"✓ Batch {batch_num}/{total_batches}: Inserted {total_inserted}/{len(records)} records")
        
        except Exception as e:
            logger.error(f"✗ Error inserting batch {batch_num}: {e}")
            logger.info(f"  Falling back to one-by-one insertion...")
            
            for record in batch:
                try:
                    supabase.table("table5").upsert(record).execute()
                    total_inserted += 1
                except Exception as record_error:
                    logger.error(f"  ✗ Failed to insert NDC {record['ndc']}: {record_error}")
    
    logger.info(f"✓ Insertion complete: {total_inserted}/{len(records)} records inserted")

# Truncate the table because we want to fully clear the data
def truncate_table5():
    """
    Truncate (delete all rows from) table5 before inserting new data.
    This ensures a fresh start with each run.
    """
    logger.info("Truncating table5 (deleting all existing rows)...")
    
    try:
        # Delete all rows from table5
        response = supabase.table("table5").delete().neq('ndc', '').execute()
        logger.info("✓ Table5 truncated successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to truncate table5: {e}")
        return False

def main():
    """Main orchestration function."""
    start_time = datetime.now()
    logger.info("="*70)
    logger.info("FDA DRUG LABEL DATA AUTOMATION - DAILY RUN")
    logger.info(f"Run started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*70)
    
    try:
        # Step 1: Setup
        logger.info("\n[STEP 1/8] Setting up work directory...")
        setup_work_directory()
        
        # Step 2: Download
        logger.info("\n[STEP 2/8] Downloading FDA data...")
        if not download_fda_data():
            raise Exception("Download failed")
        
        # Step 3: Extract main ZIP
        logger.info("\n[STEP 3/8] Extracting main ZIP file...")
        if not extract_main_zip():
            raise Exception("Main ZIP extraction failed")
        
        # Step 3.5: Find prescription directory
        logger.info("\n[STEP 3.5/8] Locating prescription directory...")
        prescription_dir = find_prescription_directory()
        if not prescription_dir:
            raise Exception("Prescription directory not found in extracted files")
        
        # Step 4: Extract prescription ZIPs
        logger.info("\n[STEP 4/8] Extracting prescription ZIP files...")
        xml_count = extract_prescription_zips(prescription_dir)
        if xml_count == 0:
            raise Exception("No XML files extracted from prescription ZIPs")
        
        # Step 5: Process XML files
        logger.info("\n[STEP 5/8] Processing XML files for NDC-DUNS mappings...")
        ndc_duns_data = process_all_xml_files()
        if not ndc_duns_data:
            raise Exception("No NDC-DUNS mappings extracted")
        
        # Step 6: Delete current data in the database(do right before insertion in case someone is using the website at the moment)
        logger.info("\n[STEP 6/8] Inserting data into Supabase...")
        truncate_table5()
        
        # Step 7: Insert to Supabase
        logger.info("\n[STEP 7/8] Inserting data into Supabase...")
        insert_to_supabase(ndc_duns_data)
        
        # Step 7: Cleanup
        logger.info("\n[STEP 8/8] Cleaning up temporary files...")
        cleanup_work_directory()
        
        # Success summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60
        
        logger.info("\n" + "="*70)
        logger.info("✓ AUTOMATION COMPLETED SUCCESSFULLY!")
        logger.info("="*70)
        logger.info(f"Run completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Total duration: {duration:.2f} minutes")
        logger.info(f"XML files processed: {xml_count}")
        logger.info(f"NDC-DUNS mappings extracted: {len(ndc_duns_data)}")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"\n✗ AUTOMATION FAILED: {e}")
        logger.info("Attempting cleanup...")
        cleanup_work_directory()
        raise


if __name__ == "__main__":
    main()