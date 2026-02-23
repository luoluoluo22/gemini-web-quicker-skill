import json
import requests
import sys
from pathlib import Path

def test_stream():
    config_path = Path(r"f:\Desktop\kaifa\jianying-editor-skill2\.agent\skills\antigravity-api-skill\libs\data\config.json")
    if not config_path.exists():
        print("[-] Config not found")
        return
        
    config = json.loads(config_path.read_text(encoding='utf-8'))
    base_url = config.get("base_url", "").rstrip("/")
    api_key = config.get("api_key", "YOUR_API_KEY_HERE")
    
    payload = {
        "model": "banana",
        "messages": [{"role": "user", "content": "Generate a beautiful 4k image of a futuristic city"}],
        "size": "1024x1024",
        "stream": True 
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print(f"[*] Starting Stream Test on {base_url}...")
    try:
        # 使用较长的超时时间，因为生图比较慢
        response = requests.post(
            f"{base_url}/chat/completions", 
            headers=headers, 
            json=payload, 
            timeout=180, 
            stream=True,
            proxies={"http": None, "https": None}
        )
        
        print(f"[+] Status Code: {response.status_code}")
        
        full_content = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                # 打印所有原始数据，不放过任何信息
                print(f"RAW: {decoded_line}")
                
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:].strip()
                    if data_str == "[DONE]":
                        print("[*] Stream Ended with [DONE]")
                        break
                    try:
                        data_json = json.loads(data_str)
                        # 打印完整 JSON 结构，用于诊断非标准字段
                        print(f"DEBUG FULL DATA: {json.dumps(data_json)}")
                        
                        choice = data_json.get("choices", [{}])[0]
                        # 尝试从各种可能的地方获取文本
                        content = (choice.get("delta", {}).get("content", "") or 
                                  choice.get("message", {}).get("content", "") or
                                  data_json.get("url", "") or  # 尝试顶级字段
                                  data_json.get("image_url", "")) # 尝试顶级字段
                        full_content += content
                    except Exception as e:
                        pass
        
        print("\n--- Final Aggregated Content ---")
        if full_content:
            print(full_content)
        else:
            print("[!] Warning: Aggregated content is empty!")
            
    except Exception as e:
        print(f"[-] Stream failed: {e}")

if __name__ == "__main__":
    test_stream()
