import json
import requests
import sys
import base64
import os
from pathlib import Path

def test_video_analysis():
    config_path = Path(r"f:\Desktop\kaifa\jianying-editor-skill2\.agent\skills\antigravity-api-skill\libs\data\config.json")
    if not config_path.exists():
        print("[-] Config not found")
        return
        
    config = json.loads(config_path.read_text(encoding='utf-8'))
    base_url = config.get("base_url", "").rstrip("/")
    api_key = config.get("api_key", "YOUR_API_KEY_HERE")
    
    video_path = r"F:\Desktop\test_output.mp4"
    if not os.path.exists(video_path):
        print(f"[-] Video not found at {video_path}")
        return

    print(f"[*] Reading and encoding video: {video_path}")
    with open(video_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode("utf-8")
    
    # 按照用户给出的结构构造 Payload
    payload = {
      "model": "gemini-3-pro",
      "stream": True,
      "messages": [
        {
          "role": "user",
          "content": "请总结这个视频的内容"
        }
      ],
      "files": [
        {
          "filename": "test_output.mp4",
          "mime_type": "video/mp4",
          "file_data": f"data:video/mp4;base64,{video_b64}"
        }
      ]
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print(f"[*] Sending Video Analysis Request (Streaming) to {base_url}...")
    try:
        response = requests.post(
            f"{base_url}/chat/completions", 
            headers=headers, 
            json=payload, 
            timeout=300, 
            stream=True,
            proxies={"http": None, "https": None}
        )
        
        print(f"[+] Status Code: {response.status_code}")
        
        full_content = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8').strip()
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:].strip()
                    if data_str == "[DONE]":
                        print("\n[*] Stream Ended with [DONE]")
                        break
                    try:
                        data_json = json.loads(data_str)
                        delta = data_json.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        print(content, end="", flush=True)
                        full_content += content
                    except:
                        pass
        
        if not full_content:
            print("\n[!] Warning: No content returned from server.")
            
    except Exception as e:
        print(f"\n[-] Request failed: {e}")

if __name__ == "__main__":
    test_video_analysis()
