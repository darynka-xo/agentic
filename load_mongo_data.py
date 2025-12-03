#!/usr/bin/env python3
"""
Load MongoDB collections from JSON export files.
Run this script to populate your MongoDB with SCP reference data.
"""

import json
import os
import sys
from pathlib import Path

from config import get_db


def load_json_file(filepath: str):
    """Load and parse a JSON file."""
    print(f"Loading {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"  Loaded {len(data) if isinstance(data, list) else 1} documents")
    return data


def load_collection(db, collection_name: str, json_file: str, drop_existing: bool = True):
    """Load a collection from a JSON file."""
    collection = db[collection_name]
    
    # Drop existing data if requested
    if drop_existing:
        count_before = collection.count_documents({})
        if count_before > 0:
            print(f"  Dropping {count_before} existing documents from {collection_name}")
            collection.drop()
    
    # Load data from JSON file
    data = load_json_file(json_file)
    
    # Ensure data is a list
    if not isinstance(data, list):
        data = [data]
    
    if not data:
        print(f"  WARNING: No data to insert for {collection_name}")
        return 0
    
    # Insert documents
    try:
        result = collection.insert_many(data, ordered=False)
        inserted_count = len(result.inserted_ids)
        print(f"  ✓ Inserted {inserted_count} documents into {collection_name}")
        return inserted_count
    except Exception as e:
        print(f"  ✗ ERROR inserting into {collection_name}: {str(e)}")
        return 0


def verify_data(db):
    """Verify that data was loaded correctly."""
    print("\n" + "=" * 60)
    print("Verifying loaded data...")
    print("=" * 60)
    
    # Check sections
    sections_count = db.sections.count_documents({})
    print(f"  Sections: {sections_count}")
    
    if sections_count > 0:
        sample_section = db.sections.find_one({})
        print(f"    Sample section code: {sample_section.get('code')}")
        
        # Check for tables in nested structure
        has_tables = False
        for subsection in sample_section.get("subsections", []):
            for chapter in subsection.get("chapters", []):
                if chapter.get("tables"):
                    has_tables = True
                    sample_table = chapter["tables"][0]
                    print(f"    Sample table code: {sample_table.get('table_code')}")
                    break
            if has_tables:
                break
    
    # Check coefficients
    coefficients_count = db.coefficients.count_documents({})
    print(f"  Coefficients: {coefficients_count}")
    
    if coefficients_count > 0:
        sample_coef = db.coefficients.find_one({})
        print(f"    Sample coefficient ID: {sample_coef.get('_id')}")
        print(f"    Sample coefficient value: {sample_coef.get('coefficient_value')}")
    
    # Check formulas
    formulas_count = db.formulas.count_documents({})
    print(f"  Formulas: {formulas_count}")
    
    # Check general provisions
    general_count = db.general_provisions.count_documents({})
    print(f"  General Provisions: {general_count}")
    
    print("\n" + "=" * 60)
    if sections_count > 0 and coefficients_count > 0:
        print("✓ Data loaded successfully!")
    else:
        print("✗ WARNING: Some collections are empty!")
    print("=" * 60)


def main():
    """Main function to load all collections."""
    # Get the workspace directory
    workspace_dir = Path(__file__).parent
    
    # Define collection files
    collections = {
        "sections": workspace_dir / "sections.json",
        "coefficients": workspace_dir / "coefficients.json",
        "formulas": workspace_dir / "formulas.json",
        "general_provisions": workspace_dir / "general_provisions.json",
    }
    
    # Check that all files exist
    missing_files = []
    for name, filepath in collections.items():
        if not filepath.exists():
            missing_files.append(str(filepath))
    
    if missing_files:
        print("ERROR: Missing required JSON files:")
        for f in missing_files:
            print(f"  - {f}")
        sys.exit(1)
    
    # Get database connection
    print("Connecting to MongoDB...")
    try:
        db = get_db()
        # Test connection
        db.command("ping")
        print("✓ Connected to MongoDB\n")
    except Exception as e:
        print(f"✗ ERROR: Could not connect to MongoDB: {str(e)}")
        print("\nMake sure MONGO_URI is set correctly in your environment.")
        sys.exit(1)
    
    # Load each collection
    print("=" * 60)
    print("Loading MongoDB collections from JSON files...")
    print("=" * 60 + "\n")
    
    total_inserted = 0
    for collection_name, json_file in collections.items():
        count = load_collection(db, collection_name, str(json_file), drop_existing=True)
        total_inserted += count
        print()
    
    print(f"Total documents inserted: {total_inserted}\n")
    
    # Verify data
    verify_data(db)


if __name__ == "__main__":
    main()

