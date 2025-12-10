#!/usr/bin/env python3
"""
Test script for OCR-based PDF processing endpoint
"""
import sys
import requests
from pathlib import Path


def test_ocr_endpoint(pdf_path: str, server_url: str = "http://127.0.0.1:8000"):
    """
    Test the /predict_pdf_ocr endpoint with a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        server_url: Base URL of the server
    """
    pdf_file = Path(pdf_path)
    
    if not pdf_file.exists():
        print(f"❌ Error: PDF file not found: {pdf_path}")
        return False
    
    print(f"📄 Testing OCR endpoint with: {pdf_file.name}")
    print(f"🔗 Server: {server_url}")
    print("-" * 60)
    
    endpoint = f"{server_url}/predict_pdf_ocr"
    
    try:
        with open(pdf_file, 'rb') as f:
            files = {'file': (pdf_file.name, f, 'application/pdf')}
            
            print("📤 Uploading PDF and processing with VLM OCR...")
            response = requests.post(endpoint, files=files, timeout=300)
        
        print(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ SUCCESS!")
            print(f"   Filename: {result.get('filename')}")
            print(f"   Processing method: {result.get('processing_method')}")
            print(f"   Tables processed: {result.get('tables_processed')}")
            
            # Show results summary
            results = result.get('results', [])
            successful = sum(1 for r in results if r.get('status') == 'success')
            failed = sum(1 for r in results if r.get('status') == 'error')
            
            print(f"\n📊 Results:")
            print(f"   Successful: {successful}")
            print(f"   Failed: {failed}")
            
            # Show OCR metadata
            for i, res in enumerate(results, 1):
                print(f"\n   Table {i}:")
                print(f"     Status: {res.get('status')}")
                print(f"     Page: {res.get('page_number', 'N/A')}")
                
                if 'ocr_metadata' in res:
                    ocr_meta = res['ocr_metadata']
                    print(f"     OCR time: {ocr_meta.get('processing_time_ms', 'N/A'):.2f}ms")
                    
                if res.get('status') == 'error':
                    print(f"     Error: {res.get('error')}")
            
            # Save full result
            output_file = pdf_file.with_suffix('.ocr_result.json')
            import json
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Full result saved to: {output_file}")
            
            return True
            
        else:
            print(f"\n❌ FAILED!")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Connection Error!")
        print(f"   Cannot connect to {server_url}")
        print(f"   Make sure the server is running:")
        print(f"   ./manage.sh start")
        return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ocr_endpoint.py <path_to_pdf>")
        print("\nExample:")
        print("  python test_ocr_endpoint.py ./ocr_service/test.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    server_url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"
    
    success = test_ocr_endpoint(pdf_path, server_url)
    sys.exit(0 if success else 1)
