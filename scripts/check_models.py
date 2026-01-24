"""
Script to test available Gemini models and check rate limits
"""
import os
import sys
sys.path.insert(0, '/home/kien/Documents/VTI/est/convert-sheet-to-md/src')

from ai_converter import AIConverter

def main():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        return
    
    print("=" * 80)
    print("Listing available Gemini models...")
    print("=" * 80)
    
    models = AIConverter.list_models(api_key)
    
    if not models:
        print("No models found or error occurred")
    else:
        print(f"\nFound {len(models)} models:")
        for i, model in enumerate(models, 1):
            print(f"  {i}. {model}")
    
    print("\n" + "=" * 80)
    print("Recommended models for batch processing (with rate limits):")
    print("=" * 80)
    
    recommended = [
        ("gemini-2.0-flash-exp", "Experimental - VERY LOW quota"),
    ]
    
    print("\nModel recommendations:")
    for model_name, desc in recommended:
        available = "✅" if model_name in models else "❌"
        print(f"  {available} {model_name:30s} - {desc}")

if __name__ == "__main__":
    main()
