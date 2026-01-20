import requests
import json
import os

# Configuration
BASE_URL = 'http://localhost:5000'
UPLOAD_URL = f'{BASE_URL}/api/upload'
CONVERT_URL = f'{BASE_URL}/api/convert'

def create_dummy_csv():
    content = "Name,Age\nTest,20"
    with open('error_test.csv', 'w') as f:
        f.write(content)
    return 'error_test.csv'

def test_error_handling():
    print("🚀 Starting Error Handling Verification...")
    
    # 1. Upload file
    csv_file = create_dummy_csv()
    files = {'files[]': open(csv_file, 'rb')}
    
    print("📤 Uploading test file...")
    requests.post(UPLOAD_URL, files=files)

    # 2. Trigger Error with Invalid Key
    payload = {
        "mode": "ai",
        "ai_config": {
            "use_custom_config": True,
            "provider": "gemini",
            "api_key": "INVALID_KEY_FOR_TESTING_ERRORS", 
            "model_name": "gemini-2.5-flash"
        }
    }
    
    print("🔄 Sending Request with Invalid Key...")
    response = requests.post(CONVERT_URL, json=payload)
    
    print(f"Response Status: {response.status_code}")
    data = response.json()
    print(f"Response Body: {json.dumps(data, indent=2)}")
    
    # Verify structure
    if 'errors' in data and len(data['errors']) > 0:
        print("✅ Success: 'errors' field found in response.")
        error_item = data['errors'][0]
        if 'file' in error_item and 'error' in error_item:
            print(f"✅ Error Details: File={error_item['file']}, Error={error_item['error']}")
        else:
            print("❌ Invalid error item structure.")
    else:
        print("❌ Failed: 'errors' field missing or empty.")

    # Clean up
    if os.path.exists(csv_file):
        os.remove(csv_file)

if __name__ == "__main__":
    test_error_handling()
