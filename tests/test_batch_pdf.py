#!/usr/bin/env python3
"""
Test the /predict_pdf endpoint with multiple PDF files.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests
from tqdm import tqdm


def test_pdf_file(filepath: Path, server_url: str) -> Dict:
    """Test a single PDF file against the API."""
    try:
        print(f"\n📄 Processing: {filepath.name}")
        
        with open(filepath, 'rb') as f:
            files = {'file': (filepath.name, f, 'application/pdf')}
            
            response = requests.post(
                server_url,
                files=files,
                timeout=300  # 5 minutes timeout
            )
        
        # Parse response
        if response.status_code == 200:
            try:
                resp_json = response.json()
                tables_processed = resp_json.get('tables_processed', 0)
                results = resp_json.get('results', [])
                success_count = sum(1 for r in results if r.get('status') == 'success')
                
                print(f"  ✅ Таблиц обработано: {tables_processed}")
                print(f"  ✅ Успешно: {success_count}/{len(results)}")
                
                return {
                    "filename": filepath.name,
                    "status": "success",
                    "http_code": response.status_code,
                    "tables_processed": tables_processed,
                    "tables_success": success_count,
                    "tables_failed": len(results) - success_count,
                    "response": resp_json,
                    "error": None
                }
            except Exception as e:
                return {
                    "filename": filepath.name,
                    "status": "failed",
                    "http_code": response.status_code,
                    "response": {"raw": response.text},
                    "error": f"Failed to parse response: {str(e)}"
                }
        else:
            # Try to parse error message
            try:
                resp_json = response.json()
                error_detail = resp_json.get('detail', response.text)
            except:
                error_detail = response.text
            
            print(f"  ❌ HTTP {response.status_code}: {error_detail[:100]}")
            
            return {
                "filename": filepath.name,
                "status": "failed",
                "http_code": response.status_code,
                "response": resp_json if 'resp_json' in locals() else None,
                "error": error_detail
            }
    
    except requests.exceptions.Timeout:
        print(f"  ❌ Timeout (>300s)")
        return {
            "filename": filepath.name,
            "status": "failed",
            "http_code": None,
            "response": None,
            "error": "Request timeout (>300s)"
        }
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
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
    results_file = output_path / f"pdf_results_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Save summary as text
    summary_file = output_path / f"pdf_summary_{timestamp}.txt"
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count
    success_rate = (success_count / len(results) * 100) if results else 0
    
    total_tables = sum(r.get('tables_processed', 0) for r in results if r['status'] == 'success')
    total_success_tables = sum(r.get('tables_success', 0) for r in results if r['status'] == 'success')
    total_failed_tables = sum(r.get('tables_failed', 0) for r in results if r['status'] == 'success')
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("BATCH PDF TEST SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Total PDF files: {len(results)}\n")
        f.write(f"Success: {success_count}\n")
        f.write(f"Failed: {failed_count}\n")
        f.write(f"Success rate: {success_rate:.2f}%\n\n")
        
        f.write(f"Total tables processed: {total_tables}\n")
        f.write(f"Tables success: {total_success_tables}\n")
        f.write(f"Tables failed: {total_failed_tables}\n\n")
        
        f.write("=" * 60 + "\n")
        f.write("SUCCESSFUL FILES\n")
        f.write("=" * 60 + "\n")
        for result in results:
            if result["status"] == "success":
                f.write(f"\n{result['filename']}\n")
                f.write(f"  Tables processed: {result.get('tables_processed', 0)}\n")
                f.write(f"  Success: {result.get('tables_success', 0)}\n")
                f.write(f"  Failed: {result.get('tables_failed', 0)}\n")
        
        f.write("\n" + "=" * 60 + "\n")
        f.write("FAILED FILES\n")
        f.write("=" * 60 + "\n")
        for result in results:
            if result["status"] == "failed":
                f.write(f"\n{result['filename']}\n")
                f.write(f"  HTTP Code: {result.get('http_code', 'N/A')}\n")
                f.write(f"  Error: {result.get('error', 'Unknown')}\n")
    
    return results_file, summary_file


def main():
    """Main function to run batch PDF tests."""
    SERVER_URL = "http://localhost:8000/predict_pdf"
    
    # Get PDF files from command line
    if len(sys.argv) < 2:
        print("Usage: python test_batch_pdf.py file1.pdf file2.pdf ...")
        sys.exit(1)
    
    pdf_paths = [Path(arg) for arg in sys.argv[1:]]
    
    # Validate files
    valid_files = []
    for pdf_path in pdf_paths:
        if not pdf_path.exists():
            print(f"⚠️  File not found: {pdf_path}")
        elif not pdf_path.name.endswith('.pdf'):
            print(f"⚠️  Not a PDF file: {pdf_path}")
        else:
            valid_files.append(pdf_path)
    
    if not valid_files:
        print("❌ No valid PDF files to test!")
        sys.exit(1)
    
    print("=" * 80)
    print("🧪 BATCH PDF TESTING")
    print("=" * 80)
    print(f"Server: {SERVER_URL}")
    print(f"Files to test: {len(valid_files)}")
    print()
    
    # Test each file
    results = []
    for i, filepath in enumerate(valid_files, 1):
        print(f"\n[{i}/{len(valid_files)}] Testing: {filepath.name}")
        print(f"Size: {filepath.stat().st_size / 1024:.1f} KB")
        
        result = test_pdf_file(filepath, SERVER_URL)
        results.append(result)
    
    # Calculate statistics
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count
    success_rate = (success_count / len(results) * 100) if results else 0
    
    total_tables = sum(r.get('tables_processed', 0) for r in results if r['status'] == 'success')
    total_success_tables = sum(r.get('tables_success', 0) for r in results if r['status'] == 'success')
    total_failed_tables = sum(r.get('tables_failed', 0) for r in results if r['status'] == 'success')
    
    # Save results
    results_file, summary_file = save_results(results)
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total PDF files: {len(results)}")
    print(f"✅ Success: {success_count} ({success_rate:.2f}%)")
    print(f"❌ Failed: {failed_count}")
    print()
    print(f"📋 Total tables processed: {total_tables}")
    print(f"✅ Tables success: {total_success_tables}")
    print(f"❌ Tables failed: {total_failed_tables}")
    print()
    print(f"💾 Results saved to: {results_file}")
    print(f"💾 Summary saved to: {summary_file}")
    print("=" * 80)
    
    # Show failures if any
    if failed_count > 0:
        print("\n❌ Failed files:")
        for result in results:
            if result["status"] == "failed":
                print(f"  • {result['filename']}")
                print(f"    Error: {result.get('error', 'Unknown')[:100]}")


if __name__ == "__main__":
    try:
        import requests
    except ImportError:
        print("Error: Required package 'requests' not installed!")
        print("Run: pip install requests")
        sys.exit(1)
    
    main()

