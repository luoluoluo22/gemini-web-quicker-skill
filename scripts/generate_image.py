import sys
import os
import time
import base64
import re
import requests
from pathlib import Path
from PIL import Image

# Add libs to path
current_dir = Path(__file__).parent
libs_path = current_dir.parent / "libs"
sys.path.append(str(libs_path))

try:
    from api_client import AntigravityClient
except ImportError:
    print("[-] Error: libs module not found")
    sys.exit(1)

def create_black_reference_image(size_str, output_dir):
    """
    根据尺寸字符串 (如 1280x720) 创建一张纯黑图作为参考。
    """
    try:
        w, h = map(int, size_str.split('x'))
        img = Image.new('RGB', (w, h), color='black')
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"ref_black_{size_str}.png"
        img.save(path)
        return path
    except Exception as e:
        print(f"[-] Failed to create reference image: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_image.py \"Prompt\" [size] [image_path]")
        return

    prompt = sys.argv[1]
    size_arg = sys.argv[2] if len(sys.argv) > 2 else "1024x1024"
    image_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    ratio_map = {
        "16:9": "1280x720",
        "9:16": "720x1280", 
        "4:3": "1024x768",
        "3:4": "768x1024",
        "1:1": "1024x1024"
    }
    
    target_size = ratio_map.get(size_arg, size_arg)
    
    # [优化]: 将尺寸控制逻辑结合进提示词 (Prompt Injection)
    # Gemini 网页版对 "16:9 aspect ratio", "widescreen", "portrait" 等词汇更敏感
    enhanced_prompt = prompt
    if size_arg == "16:9":
        if "16:9" not in prompt and "widescreen" not in prompt.lower():
            enhanced_prompt = f"{prompt}, widescreen, cinematic wide shot, 16:9 aspect ratio"
    elif size_arg == "9:16":
        if "9:16" not in prompt and "portrait" not in prompt.lower():
            enhanced_prompt = f"{prompt}, portrait, vertical poster, phone wallpaper format, 9:16 aspect ratio"
    elif size_arg == "4:3":
        if "4:3" not in prompt and "landscape" not in prompt.lower():
            enhanced_prompt = f"{prompt}, standard landscape, 4:3 aspect ratio"
    elif size_arg == "3:4":
        if "3:4" not in prompt and "portrait" not in prompt.lower():
            enhanced_prompt = f"{prompt}, standard portrait, 3:4 aspect ratio"
    elif size_arg:
        if size_arg not in prompt:
            enhanced_prompt = f"{prompt}, {size_arg} aspect ratio"
    
    def create_blank_reference_image(size_str, output_dir):
        """
        根据尺寸字符串创建一个纯白画布。使用白底（代表空白画板）或随机噪点更不容易影响最终成图的色调。
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / f"ref_blank_{size_str}.png"
            # [持久化缓存]: 如果该比例的白底图已存在，直接复用，不重复创建
            if not path.exists():
                w, h = map(int, size_str.split('x'))
                img = Image.new('RGB', (w, h), color='white')
                img.save(path)
            return path
        except Exception as e:
            print(f"[-] Failed to create reference image: {e}")
            return None

    ref_image_path = image_path
    if not ref_image_path and size_arg in ratio_map and size_arg != "1:1":
        # 将参考白底图持久化存储在技能的 resources 目录中
        ref_dir = current_dir.parent / "resources" / "aspect_ratios"
        ref_image_path = create_blank_reference_image(target_size, ref_dir)
        print(f"[*] Using blank reference image for ratio {size_arg} ({target_size}): {ref_image_path}")
        # 添加防污染提示词，告诉模型仅仅使用这张图作为宽高比模板
        if ref_image_path:
            enhanced_prompt += " (IMPORTANT STRICT INSTRUCTION: The attached image is just a blank white canvas. IGNORING its color and content entirely. Generate the image purely based on the text prompt and fill the entire scene with appropriate, rich, and vibrant colors. ONLY use the attached image to MATCH the ASPECT RATIO)."
    
    client = AntigravityClient()
    print(f"[*] Final Prompt: {enhanced_prompt}")
    res = client.generate_image(enhanced_prompt, size=target_size, image_path=str(ref_image_path) if ref_image_path else None)
    
    if res and "choices" in res:
        content = res["choices"][0].get("message", {}).get("content", "")
        print(f"[*] Response content received (Length: {len(content)})")
        
        save_dir = Path(os.getcwd()) / "generated_assets"
        save_dir.mkdir(parents=True, exist_ok=True)
        saved_any = False

        # 1. 优先从 Markdown 语法中寻找图片 URL: ![](URL)
        markdown_urls = re.findall(r"!\[.*?\]\((http[s]?://[^\s\)]+)\)", content)
        
        # 2. 如果没找到，再尝试寻找纯文本中的 URL
        if not markdown_urls:
            plain_urls = re.findall(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+=]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", content)
            # 过滤掉末尾可能被误抓的括号（如果是成对出现的 URL 内部括号除外，但通常末尾的是包装括号）
            urls = [u.rstrip(')') for u in plain_urls]
        else:
            urls = markdown_urls

        if urls:
            for i, url in enumerate(urls):
                try:
                    # 清理 URL (移除末尾可能的 Markdown 干扰字符)
                    url = url.split(')')[0] if ')' in url and '(' not in url else url
                    
                    print(f"[*] Downloading image from {url}...")
                    img_resp = requests.get(url, timeout=30)
                    if img_resp.status_code == 200:
                        fname = f"antigravity_{int(time.time())}_url_{i}.png"
                        save_path = save_dir / fname
                        save_path.write_bytes(img_resp.content)
                        print(f"[+] Image saved: {save_path}")
                        saved_any = True
                    else:
                        print(f"[-] Download failed (Status {img_resp.status_code}) for URL: {url}")
                except Exception as e:
                    print(f"[-] Download failed: {e}")

        # 2. Look for Base64 Data (common in Markdown or raw)
        # Pattern: data:image/png;base64,xxxx or just long base64 string inside parentheses
        b64_matches = re.findall(r"data:image\/[a-zA-Z]+;base64,([a-zA-Z0-9+/=]+)", content)
        if not b64_matches:
            # Try to find base64-like blobs in Markdown image syntax ![alt](data:...)
            b64_matches = re.findall(r"base64,([a-zA-Z0-9+/=]{100,})", content)

        if b64_matches:
            for i, b64_str in enumerate(b64_matches):
                try:
                    print(f"[*] Decoding Base64 image {i}...")
                    img_data = base64.b64decode(b64_str)
                    fname = f"antigravity_{int(time.time())}_b64_{i}.png"
                    save_path = save_dir / fname
                    save_path.write_bytes(img_data)
                    print(f"[+] Image saved: {save_path}")
                    saved_any = True
                except Exception as e:
                    print(f"[-] Base64 decode failed: {e}")

        if not saved_any:
            print("[-] No image URL or Base64 data found in response")
            if len(content) > 200:
                print(f"[*] Content snippet: {content[:200]}...")
    else:
        print("[-] Generation failed")

if __name__ == "__main__":
    main()
