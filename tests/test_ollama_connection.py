#!/usr/bin/env python3
"""
Test script to verify Ollama connection and model availability.
Run this on your RunPod instance to diagnose LLM connection issues.
"""

import os
import sys
import requests
import time


def test_ollama_connection():
    """Test if Ollama server is accessible and responding."""
    
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "ollama/qwen3:30b")
    
    # Remove ollama/ prefix for direct Ollama API calls
    model_name = model.replace("ollama/", "")
    
    print(f"Testing Ollama connection...")
    print(f"Base URL: {base_url}")
    print(f"Model: {model_name}")
    print("-" * 60)
    
    # Test 1: Check if Ollama server is running
    try:
        print("\n1. Checking if Ollama server is accessible...")
        response = requests.get(f"{base_url}/api/tags", timeout=10)
        print(f"   ✓ Server is accessible (Status: {response.status_code})")
        
        if response.status_code == 200:
            available_models = response.json().get("models", [])
            print(f"   Available models: {[m['name'] for m in available_models]}")
            
            # Check if our model is available
            model_found = any(model_name in m['name'] for m in available_models)
            if model_found:
                print(f"   ✓ Model '{model_name}' is available")
            else:
                print(f"   ✗ WARNING: Model '{model_name}' NOT found!")
                print(f"   You may need to pull it first: ollama pull {model_name}")
    except requests.exceptions.ConnectionError:
        print(f"   ✗ FAILED: Cannot connect to Ollama server at {base_url}")
        print(f"   Make sure Ollama is running: 'ollama serve'")
        return False
    except Exception as e:
        print(f"   ✗ FAILED: {str(e)}")
        return False
    
    # Test 2: Try a simple completion
    try:
        print("\n2. Testing model inference...")
        payload = {
            "model": model_name,
            "prompt": "Say 'test successful' and nothing else.",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 50
            }
        }
        
        print(f"   Sending test prompt to {base_url}/api/generate...")
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=120
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            generated_text = result.get("response", "")
            print(f"   ✓ Model responded in {elapsed:.2f}s")
            print(f"   Response: {generated_text[:200]}")
            
            if not generated_text or generated_text.strip() == "":
                print(f"   ✗ WARNING: Model returned empty response!")
                return False
        else:
            print(f"   ✗ FAILED: Status {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"   ✗ FAILED: Request timed out after 120s")
        print(f"   The model might be too slow or not loaded in memory")
        return False
    except Exception as e:
        print(f"   ✗ FAILED: {str(e)}")
        return False
    
    print("\n" + "=" * 60)
    print("✓ All tests passed! Ollama is working correctly.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_ollama_connection()
    sys.exit(0 if success else 1)

