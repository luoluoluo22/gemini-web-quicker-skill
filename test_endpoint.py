import json
import requests
import sys
from pathlib import Path

def test():
    config_path = Path(r"f:\Desktop\kaifa\jianying-editor-skill2\.agent\skills\antigravity-api-skill\libs\data\config.json")
    if not config_path.exists():
        print(f"[-] Config not found at {config_path}")
        return

    config = json.loads(config_path.read_text(encoding='utf-8'))
    base_url = config.get("base_url", "").rstrip("/")
    api_key = config.get("api_key", "sk-antigravity") # Default if placeholder
    
    print(f"[*] Testing Endpoint: {base_url}")
    print(f"[*] API Key: {api_key[:8]}...")

    payload = {
        "model": "banana",
        "messages": [{"role": "user", "content": "Generate a beautiful 4k image of a futuristic city"}],
        "size": "1024x1024",
        "stream": False
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        print("[*] Sending request to /chat/completions...")
        # Use a shorter timeout for testing
        response = requests.post(
            f"{base_url}/chat/completions", 
            headers=headers, 
            json=payload, 
            timeout=180, # Image generation can be slow
            proxies={"http": None, "https": None} # Disable system proxies for localhost
        )
        print(f"[+] Status Code: {response.status_code}")
        print("\n[+] Response Body:")
        print(response.text)
        
        if response.status_code == 200:
            try:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print("\n[*] Extracted Content:")
                print(content)
            except Exception as eje:
                print(f"[-] JSON Parse Error: {eje}")
    except requests.exceptions.Timeout:
        print("[-] Request Timed Out (Manager might be processing or stuck)")
    except Exception as e:
        print(f"[-] Request failed: {e}")

if __name__ == "__main__":
    test()
