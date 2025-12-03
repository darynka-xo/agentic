#!/usr/bin/env python3
"""
Test the /predict endpoint with multiple files from tabula_tables directory.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests
from tqdm import tqdm


def find_tabula_files(directory: str = "tabula_tables", max_files: int = 50) -> List[Path]:
    """Find JSON files in tabula_tables directory."""
    tabula_dir = Path(directory)
    if not tabula_dir.exists():
        print(f"Error: Directory {directory} not found!")
        sys.exit(1)
    
    files = sorted(tabula_dir.glob("*.json"))[:max_files]
    return files


def test_file(filepath: Path, server_url: str) -> Dict:
    """Test a single file against the API."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        
        response = requests.post(
            server_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120  # 2 minutes timeout
        )
        
        return {
            "filename": filepath.name,
            "status": "success" if response.status_code == 200 else "failed",
            "http_code": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text,
            "error": None
        }
    
    except requests.exceptions.Timeout:
        return {
            "filename": filepath.name,
            "status": "failed",
            "http_code": None,
            "response": None,
            "error": "Request timeout (>120s)"
        }
    except Exception as e:
        return {
            "filename": filepath.name,
            "status": "failed",
            "http_code": None,
            "response": None,
            "error": str(e)
        }


def save_results(results: List[Dict], output_dir: str = "batch_results"):
    """Save test results to files."""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save full results as JSON
    results_file = output_path / f"results_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Save summary as text
    summary_file = output_path / f"summary_{timestamp}.txt"
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count
    success_rate = (success_count / len(results) * 100) if results else 0
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("BATCH TEST SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Total files: {len(results)}\n")
        f.write(f"Success: {success_count}\n")
        f.write(f"Failed: {failed_count}\n")
        f.write(f"Success rate: {success_rate:.2f}%\n\n")
        
        f.write("=" * 60 + "\n")
        f.write("FAILED FILES\n")
        f.write("=" * 60 + "\n")
        for result in results:
            if result["status"] == "failed":
                f.write(f"\n{result['filename']}\n")
                f.write(f"  HTTP Code: {result.get('http_code', 'N/A')}\n")
                f.write(f"  Error: {result.get('error', 'Unknown')}\n")
                if result.get('response'):
                    f.write(f"  Response: {result['response'][:200]}\n")
    
    return results_file, summary_file


def main():
    """Main function to run batch tests."""
    SERVER_URL = "http://localhost:8000/predict"
    MAX_FILES = 50
    
    print("=" * 60)
    print("BATCH TESTING TABULA FILES")
    print("=" * 60)
    print(f"Server: {SERVER_URL}")
    print(f"Max files: {MAX_FILES}")
    print()
    
    # Find files
    print("Finding JSON files...")
    files = find_tabula_files(max_files=MAX_FILES)
    print(f"Found {len(files)} files to test\n")
    
    if not files:
        print("No JSON files found in tabula_tables directory!")
        sys.exit(1)
    
    # Test each file with progress bar
    results = []
    print("Testing files...")
    for filepath in tqdm(files, desc="Progress", unit="file"):
        result = test_file(filepath, SERVER_URL)
        results.append(result)
        
        # Show status for each file
        status_icon = "✓" if result["status"] == "success" else "✗"
        tqdm.write(f"  {status_icon} {result['filename']}: {result['status']}")
    
    # Calculate statistics
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count
    success_rate = (success_count / len(results) * 100) if results else 0
    
    # Save results
    results_file, summary_file = save_results(results)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total processed: {len(results)}")
    print(f"Success: {success_count} ({success_rate:.2f}%)")
    print(f"Failed: {failed_count}")
    print()
    print(f"Results saved to: {results_file}")
    print(f"Summary saved to: {summary_file}")
    print("=" * 60)
    
    # Show first few failures if any
    if failed_count > 0:
        print("\nFirst 3 failures:")
        for i, result in enumerate([r for r in results if r["status"] == "failed"][:3], 1):
            print(f"  {i}. {result['filename']}")
            print(f"     Error: {result.get('error', result.get('response', 'Unknown'))}")


if __name__ == "__main__":
    # Check if requests is installed
    try:
        import requests
        from tqdm import tqdm
    except ImportError:
        print("Error: Required packages not installed!")
        print("Run: pip install requests tqdm")
        sys.exit(1)
    
    main()

