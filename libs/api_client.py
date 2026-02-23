import json
import os
import sys
from pathlib import Path
import requests
import base64
import mimetypes
import subprocess
import tempfile
import time

# Globally disable proxies to prevent localhost connection issues
s = requests.Session()
s.trust_env = False


class AntigravityClient:
    def __init__(self):
        self.config = self._load_config()
        self.base_url = self.config.get("base_url", "").rstrip("/")
        self.api_key = self.config.get("api_key", "")
        
        if not self.base_url or not self.api_key:
            print("[-] Error: Configuration missing base_url or api_key", file=sys.stderr)
            sys.exit(1)
            
    def _load_config(self):
        # [Fix] 支持 PyInstaller 打包后的路径
        paths_to_check = []
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            paths_to_check.append(exe_dir / "data" / "config.json")
            if hasattr(sys, '_MEIPASS'):
                paths_to_check.append(Path(sys._MEIPASS) / "data" / "config.json")

        current_dir = Path(__file__).parent
        paths_to_check.append(current_dir / "data" / "config.json")
        paths_to_check.append(Path.cwd() / "data" / "config.json")

        # 增加对 example 配置的回退支持 (实现零配置启动)
        paths_to_check.append(current_dir / "data" / "config.example.json")

        for p in paths_to_check:
            if p and p.exists():
                try:
                    config = json.loads(p.read_text(encoding='utf-8'))
                    if p.name.endswith(".example.json"):
                        print(f"[*] Config not found, using default template: {p.name}", file=sys.stderr)
                    return config
                except:
                    continue

        print(f"[-] Warning: No config or example found.", file=sys.stderr)
        return {}

    def _optimize_video(self, input_path, mute=False):
        """
        Use FFmpeg to compress large videos to a manageable size for AI.
        Target: 360P at low bitrate, keeping timing intact.
        """
        # Save to current working directory cache instead of temp
        cache_dir = Path("video_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Consistent naming for caching based on modification time, name and mute status
        mtime = int(os.path.getmtime(input_path))
        safe_name = os.path.basename(input_path).replace(" ", "_")
        mute_suffix = "_muted" if mute else ""
        output_path = cache_dir / f"optimized_{mtime}{mute_suffix}_{safe_name}"

        if output_path.exists() and output_path.stat().st_size > 0:
            if mute:
                print(f"[*] 使用已缓存的压缩视频 (已静音): {output_path}", file=sys.stderr)
            return str(output_path)

        print(f"[*] 正在为 AI 分析优化视频: {os.path.basename(input_path)}...", file=sys.stderr)
        if mute:
            print("[!] 提示：为了极速上传，本次压缩已移除音频数据。", file=sys.stderr)
        else:
            print("[*] 提示：正在尝试保留原声压缩，如上传过慢可尝试在指令中要求“静音分析”。", file=sys.stderr)

        audio_opt = ['-an'] if mute else ['-c:a', 'aac', '-b:a', '64k']

        try:
            # 优先尝试 GPU 加速
            try:
                print(f"[*] 尝试硬件加速 (NVENC) 压缩...", file=sys.stderr)
                gpu_cmd = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-c:v', 'h264_nvenc', '-preset', 'fast', '-cq', '38',
                    '-vf', 'scale=-2:360,fps=10'
                ] + audio_opt + [str(output_path)]
                subprocess.run(gpu_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except Exception:
                # 回退到 CPU
                print(f"[*] 硬件加速不可用，切换到 CPU (Ultrafast) 压缩...", file=sys.stderr)
                cpu_cmd = [
                    'ffmpeg', '-y', '-i', input_path,
                    '-vcodec', 'libx264', '-crf', '35', '-preset', 'ultrafast',
                    '-vf', 'scale=-2:360,fps=10'
                ] + audio_opt + [str(output_path)]
                subprocess.run(cpu_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            new_size = os.path.getsize(output_path)
            print(f"[+] 优化完成: {new_size/1024/1024:.2f}MB", file=sys.stderr)
            return str(output_path)
        except Exception as e:
            print(f"[-] 优化失败 (FFmpeg 可能未安装或文件损坏): {e}", file=sys.stderr)
            return input_path # Fallback to original

    def upload_file(self, file_path):
        """
        Stream large files to the server using the /files endpoint.
        Try multiple formats and endpoints for compatibility.
        """
        if not os.path.exists(file_path):
            return None
            
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"
        
        if file_path.lower().endswith(('.mp4', '.mov', '.webm')):
            mime_type = mime_type if "video" in mime_type else "video/mp4"

        print(f"[*] Uploading {file_name} ({file_size/1024/1024:.2f}MB)...", file=sys.stderr)
        
        # Try a few common endpoints
        endpoints = [f"{self.base_url}/files"]
        if "/v1" in self.base_url:
            endpoints.append(self.base_url.replace("/v1", "") + "/files")
            endpoints.append(self.base_url.replace("/v1", "/upload/v1") + "/files")
            endpoints.append(self.base_url.replace("/v1", "/upload/v1beta") + "/files")
            
        for url in endpoints:
            try:
                # Mode 1: Multipart (Standard OpenAI compatible)
                with open(file_path, "rb") as f:
                    files = {
                        'file': (file_name, f, mime_type),
                        'purpose': (None, 'fine-tune')
                    }
                    headers = {"Authorization": f"Bearer {self.api_key}"}
                    response = s.post(url, headers=headers, files=files, timeout=600)
                
                if response.status_code == 200:
                    result = response.json()
                    file_uri = result.get("file_uri") or result.get("id") or result.get("uri")
                    if file_uri:
                        print(f"[+] Upload success: {file_uri}")
                        return {"uri": file_uri, "mime_type": mime_type}
                else:
                    print(f"[-] Mode 1 failed ({response.status_code}) for {url}: {response.text[:100]}", file=sys.stderr)
                
                # Mode 2: Octet-stream
                with open(file_path, "rb") as f:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "X-File-Name": file_name,
                        "X-File-Type": mime_type,
                        "Content-Type": "application/octet-stream"
                    }
                    response = s.post(url, headers=headers, data=f, timeout=600)
                
                if response.status_code == 200:
                    result = response.json()
                    file_uri = result.get("file_uri") or result.get("uri")
                    if file_uri:
                        print(f"[+] Upload success: {file_uri}")
                        return {"uri": file_uri, "mime_type": mime_type}
                else:
                    print(f"[-] Mode 2 failed ({response.status_code}) for {url}: {response.text[:100]}", file=sys.stderr)
                        
            except Exception as e:
                print(f"[-] Attempt failed for {url}: {e}", file=sys.stderr)
                
        return None

    def chat_completion(self, messages, model=None, temperature=0.7, file_paths=None, file_path=None):
        url = f"{self.base_url}/chat/completions"
        model = model or self.config.get("default_chat_model", "gemini-3-flash")
        
        paths = []
        if file_path: paths.append(file_path)
        if file_paths:
            if isinstance(file_paths, list): paths.extend(file_paths)
            else: paths.append(file_paths)
            
        files_payload = []
        
        for path in paths:
            if not os.path.exists(path): continue
            
            # 智能优化：如果视频太大，先压缩。
            is_video = path.lower().endswith(('.mp4', '.mov', '.webm'))
            file_size = os.path.getsize(path)
            
            working_path = path
            # [生产模式]: 视频超过 100MB 时自动执行 AI 优化压缩
            if is_video and file_size > 100 * 1024 * 1024:
                working_path = self._optimize_video(path)
            
            try:
                mime_type, _ = mimetypes.guess_type(working_path)
                # 强制修正常见视频格式的 mime_type
                if is_video: mime_type = "video/mp4"
                mime_type = mime_type or "application/octet-stream"
                
                print(f"[*] Encoding media for files-payload: {os.path.basename(working_path)}", file=sys.stderr)
                with open(working_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("utf-8")
                
                files_payload.append({
                    "filename": os.path.basename(path),
                    "mime_type": mime_type,
                    "file_data": f"data:{mime_type};base64,{b64_data}"
                })
            except Exception as e:
                print(f"[-] Failed to process {path}: {e}", file=sys.stderr)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        
        # 如果有文件，注入顶级 files 字段 (Antigravity 专有协议)
        if files_payload:
            payload["files"] = files_payload

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Antigravity/4.0.6" 
        }
        
        try:
            # 打印负载概览
            file_size_total = sum(len(f["file_data"]) for f in files_payload) / 1024 / 1024 if files_payload else 0
            print(f"[*] Sending Payload ({file_size_total:.1f}MB media) to {url}...", file=sys.stderr)
            
            response = s.post(url, headers=headers, json=payload, stream=True, timeout=900) 
            
            # --- 自动降级逻辑 (Fallback) ---
            if response.status_code == 503 and model == "gemini-3-pro":
                print(f"[!] gemini-3-pro 返回 503 (繁忙)，自动切换到 gemini-3-flash 重试...", file=sys.stderr)
                payload["model"] = "gemini-3-flash"
                response = s.post(url, headers=headers, json=payload, stream=True, timeout=900)
            
            if response.status_code != 200:
                print(f"[-] Request failed with status {response.status_code}: {response.text}", file=sys.stderr)
                
            return response
        except Exception as e:
            print(f"[-] Request failed: {e}", file=sys.stderr)
            return None

    def generate_image(self, prompt, size="1024x1024", image_path=None, quality="standard", n=1):
        """
        [协议修正]: 完全采用原生 urllib 进行文件上传和流式处理，修复 requests 库在此场景下的边界问题。
        """
        url = f"{self.base_url}/chat/completions"
        model = self.config.get("default_image_model", "gemini-3-flash-image")
        
        # 统一使用顶级 files 字段传输文件 (Antigravity 专有协议)
        files_payload = []
        if image_path and os.path.exists(image_path):
            try:
                mime_type, _ = mimetypes.guess_type(image_path)
                mime_type = mime_type or "image/png"
                print(f"[*] Encoding reference image for files-payload: {os.path.basename(image_path)}", file=sys.stderr)
                with open(image_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("ascii")
                
                # 完全按照 test_image_upload.py 的 payload.files 格式
                files_payload.append({
                    "filename": os.path.basename(image_path),
                    "mime_type": mime_type,
                    "file_data": f"data:{mime_type};base64,{b64_data}"
                })
            except Exception as e:
                print(f"[-] Failed to process reference image {image_path}: {e}", file=sys.stderr)

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "size": size,
            "stream": True # 强制流式
        }
        
        if files_payload:
            payload["files"] = files_payload
            print(f"[*] Injected reference image into payload['files']", file=sys.stderr)
        
        print(f"[*] Sending Image Request (urllib Native Protocol) to {model}...", file=sys.stderr)
        
        import urllib.request
        import urllib.error
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            method="POST",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }
        )
        
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                content_type = (resp.headers.get("Content-Type") or "").lower()
                full_content = ""
                
                if "text/event-stream" not in content_type:
                    raw = resp.read().decode("utf-8", errors="replace")
                    try:
                        obj = json.loads(raw)
                        full_content = obj.get("choices", [{}])[0].get("message", {}).get("content", "")
                    except Exception:
                        pass
                else:
                    for raw_line in resp:
                        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                        if not line or not line.startswith("data:"):
                            continue
                            
                        data_str = line[5:].strip()
                        if data_str == "[DONE]": 
                            break

                        try:
                            obj = json.loads(data_str)
                            delta = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                full_content += delta
                        except Exception:
                            continue
                
                print(f"[*] Response content received (Length: {len(full_content)})", file=sys.stderr)
                if len(full_content) < 500:
                    print(f"[*] Response details: {full_content}", file=sys.stderr)
                
                return {
                    "choices": [{
                        "message": {"content": full_content}
                    }]
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"[-] HTTP Error {e.code}: {err_body[:500]}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[-] Image Request failed: {e}", file=sys.stderr)
            return None

    def get_models(self):
        url = f"{self.base_url}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Antigravity/4.0.6"
        }
        
        try:
            response = s.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Unified parsing: some APIs return {'data': [...]}, some return list directly
                if isinstance(data, dict) and 'data' in data:
                    return data['data']
                elif isinstance(data, list):
                    return data
                return []
            else:
                print(f"[-] API Error {response.status_code}: {response.text}")
                return []
        except Exception as e:
            print(f"[-] Models Request failed: {e}", file=sys.stderr)
            return []
