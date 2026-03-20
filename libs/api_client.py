import base64
import json
import mimetypes
import os
import subprocess
import sys
from pathlib import Path

import requests

# 全局禁用系统代理，避免本地 localhost 被代理拦截。
s = requests.Session()
s.trust_env = False

PREFERRED_CHAT_MODELS = [
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-pro",
    "gemini-3-flash",
    "gemini-thinking",
    "gemini-web-api",
]

PREFERRED_IMAGE_MODELS = [
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image",
    "gemini-3-image",
    "gemini-3-flash-image",
]

MODEL_FALLBACKS = {
    "gemini-3.1-pro-preview": ["gemini-3.1-flash-lite-preview", "gemini-3-pro", "gemini-3-flash"],
    "gemini-3.1-flash-image-preview": ["gemini-3-pro-image", "gemini-3-image", "gemini-3-flash-image"],
    "gemini-3-pro": ["gemini-3-flash"],
}


class AntigravityClient:
    def __init__(self):
        self.config = self._load_config()
        self.base_url = self.config.get("base_url", "").rstrip("/")
        self.api_key = self.config.get("api_key", "")

        if not self.base_url or not self.api_key:
            print("[-] Error: Configuration missing base_url or api_key", file=sys.stderr)
            sys.exit(1)

    def _load_config(self):
        paths_to_check = []
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).parent
            paths_to_check.append(exe_dir / "data" / "config.json")
            if hasattr(sys, "_MEIPASS"):
                paths_to_check.append(Path(sys._MEIPASS) / "data" / "config.json")

        current_dir = Path(__file__).parent
        paths_to_check.append(current_dir / "data" / "config.json")
        paths_to_check.append(Path.cwd() / "data" / "config.json")
        paths_to_check.append(current_dir / "data" / "config.example.json")

        for path in paths_to_check:
            if not path or not path.exists():
                continue
            try:
                config = json.loads(path.read_text(encoding="utf-8"))
                if path.name.endswith(".example.json"):
                    print(f"[*] Config not found, using default template: {path.name}", file=sys.stderr)
                return config
            except Exception:
                continue

        print("[-] Warning: No config or example found.", file=sys.stderr)
        return {}

    def _default_chat_model(self):
        return self.config.get("default_chat_model", PREFERRED_CHAT_MODELS[0])

    def _default_image_model(self):
        return self.config.get("default_image_model", PREFERRED_IMAGE_MODELS[0])

    def _preferred_model_entries(self):
        return [{"id": model_id} for model_id in [*PREFERRED_CHAT_MODELS, *PREFERRED_IMAGE_MODELS]]

    def _merge_models(self, models):
        merged = []
        seen = set()

        for item in self._preferred_model_entries() + models:
            model_id = item.get("id") if isinstance(item, dict) else str(item)
            if model_id in seen:
                continue
            seen.add(model_id)
            merged.append(item if isinstance(item, dict) else {"id": model_id})

        return merged

    def _should_retry_with_fallback(self, status_code, body):
        if status_code == 503:
            return True
        if status_code not in (400, 404, 422):
            return False

        lowered = (body or "").lower()
        return any(marker in lowered for marker in ["model", "not found", "unsupported", "invalid"])

    def _optimize_video(self, input_path, mute=False):
        cache_dir = Path("video_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)

        mtime = int(os.path.getmtime(input_path))
        safe_name = os.path.basename(input_path).replace(" ", "_")
        mute_suffix = "_muted" if mute else ""
        output_path = cache_dir / f"optimized_{mtime}{mute_suffix}_{safe_name}"

        if output_path.exists() and output_path.stat().st_size > 0:
            if mute:
                print(f"[*] Using cached optimized muted video: {output_path}", file=sys.stderr)
            return str(output_path)

        print(f"[*] Optimizing video for AI analysis: {os.path.basename(input_path)}...", file=sys.stderr)
        if mute:
            print("[!] Audio track will be removed to accelerate upload.", file=sys.stderr)
        else:
            print("[*] Preserving audio when possible during optimization.", file=sys.stderr)

        audio_opt = ["-an"] if mute else ["-c:a", "aac", "-b:a", "64k"]

        try:
            try:
                print("[*] Trying NVENC acceleration for video optimization...", file=sys.stderr)
                gpu_cmd = [
                    "ffmpeg", "-y", "-i", input_path,
                    "-c:v", "h264_nvenc", "-preset", "fast", "-cq", "38",
                    "-vf", "scale=-2:360,fps=10",
                    *audio_opt,
                    str(output_path),
                ]
                subprocess.run(gpu_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except Exception:
                print("[*] NVENC unavailable, falling back to CPU compression...", file=sys.stderr)
                cpu_cmd = [
                    "ffmpeg", "-y", "-i", input_path,
                    "-vcodec", "libx264", "-crf", "35", "-preset", "ultrafast",
                    "-vf", "scale=-2:360,fps=10",
                    *audio_opt,
                    str(output_path),
                ]
                subprocess.run(cpu_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            new_size = os.path.getsize(output_path)
            print(f"[+] Optimization complete: {new_size / 1024 / 1024:.2f}MB", file=sys.stderr)
            return str(output_path)
        except Exception as e:
            print(f"[-] Video optimization failed: {e}", file=sys.stderr)
            return input_path

    def upload_file(self, file_path):
        if not os.path.exists(file_path):
            return None

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        if file_path.lower().endswith((".mp4", ".mov", ".webm")):
            mime_type = mime_type if "video" in mime_type else "video/mp4"

        print(f"[*] Uploading {file_name} ({file_size / 1024 / 1024:.2f}MB)...", file=sys.stderr)

        endpoints = [f"{self.base_url}/files"]
        if "/v1" in self.base_url:
            endpoints.append(self.base_url.replace("/v1", "") + "/files")
            endpoints.append(self.base_url.replace("/v1", "/upload/v1") + "/files")
            endpoints.append(self.base_url.replace("/v1", "/upload/v1beta") + "/files")

        for url in endpoints:
            try:
                with open(file_path, "rb") as f:
                    files = {
                        "file": (file_name, f, mime_type),
                        "purpose": (None, "fine-tune"),
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

                with open(file_path, "rb") as f:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "X-File-Name": file_name,
                        "X-File-Type": mime_type,
                        "Content-Type": "application/octet-stream",
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
        selected_model = model or self._default_chat_model()

        paths = []
        if file_path:
            paths.append(file_path)
        if file_paths:
            if isinstance(file_paths, list):
                paths.extend(file_paths)
            else:
                paths.append(file_paths)

        files_payload = []
        for path in paths:
            if not os.path.exists(path):
                continue

            is_video = path.lower().endswith((".mp4", ".mov", ".webm"))
            working_path = path
            if is_video and os.path.getsize(path) > 100 * 1024 * 1024:
                working_path = self._optimize_video(path)

            try:
                mime_type, _ = mimetypes.guess_type(working_path)
                if is_video:
                    mime_type = "video/mp4"
                mime_type = mime_type or "application/octet-stream"

                print(f"[*] Encoding media for files-payload: {os.path.basename(working_path)}", file=sys.stderr)
                with open(working_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("utf-8")

                files_payload.append({
                    "filename": os.path.basename(path),
                    "mime_type": mime_type,
                    "file_data": f"data:{mime_type};base64,{b64_data}",
                })
            except Exception as e:
                print(f"[-] Failed to process {path}: {e}", file=sys.stderr)

        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if files_payload:
            payload["files"] = files_payload

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Antigravity/4.0.6",
        }

        try:
            file_size_total = sum(len(f["file_data"]) for f in files_payload) / 1024 / 1024 if files_payload else 0
            print(f"[*] Sending Payload ({file_size_total:.1f}MB media) to {url}...", file=sys.stderr)

            attempt_models = [selected_model, *MODEL_FALLBACKS.get(selected_model, [])]
            response = None

            for attempt_index, attempt_model in enumerate(attempt_models):
                payload["model"] = attempt_model
                response = s.post(url, headers=headers, json=payload, stream=True, timeout=900)
                if response.status_code == 200:
                    break

                if attempt_index == len(attempt_models) - 1:
                    break

                if not self._should_retry_with_fallback(response.status_code, getattr(response, "text", "")):
                    break

                print(f"[!] {attempt_model} unavailable, retrying with fallback model...", file=sys.stderr)

            if response is not None and response.status_code != 200:
                print(f"[-] Request failed with status {response.status_code}: {response.text}", file=sys.stderr)
            return response
        except Exception as e:
            print(f"[-] Request failed: {e}", file=sys.stderr)
            return None

    def generate_image(self, prompt, size="1024x1024", image_path=None, quality="standard", n=1):
        url = f"{self.base_url}/chat/completions"
        selected_model = self._default_image_model()

        files_payload = []
        if image_path and os.path.exists(image_path):
            try:
                mime_type, _ = mimetypes.guess_type(image_path)
                mime_type = mime_type or "image/png"
                print(f"[*] Encoding reference image for files-payload: {os.path.basename(image_path)}", file=sys.stderr)
                with open(image_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("ascii")

                files_payload.append({
                    "filename": os.path.basename(image_path),
                    "mime_type": mime_type,
                    "file_data": f"data:{mime_type};base64,{b64_data}",
                })
            except Exception as e:
                print(f"[-] Failed to process reference image {image_path}: {e}", file=sys.stderr)

        payload = {
            "model": selected_model,
            "messages": [{"role": "user", "content": prompt}],
            "size": size,
            "stream": True,
        }
        if files_payload:
            payload["files"] = files_payload
            print("[*] Injected reference image into payload['files']", file=sys.stderr)

        import urllib.error
        import urllib.request

        attempt_models = [selected_model, *MODEL_FALLBACKS.get(selected_model, [])]

        for attempt_index, attempt_model in enumerate(attempt_models):
            payload["model"] = attempt_model
            print(f"[*] Sending Image Request (urllib Native Protocol) to {attempt_model}...", file=sys.stderr)

            request_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url=url,
                method="POST",
                data=request_data,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
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

                    return {"choices": [{"message": {"content": full_content}}]}
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                if attempt_index < len(attempt_models) - 1 and self._should_retry_with_fallback(e.code, err_body):
                    print(f"[!] {attempt_model} unavailable for image generation, retrying with fallback model...", file=sys.stderr)
                    continue
                print(f"[-] HTTP Error {e.code}: {err_body[:500]}", file=sys.stderr)
                return None
            except Exception as e:
                print(f"[-] Image Request failed: {e}", file=sys.stderr)
                return None

        return None

    def get_models(self):
        url = f"{self.base_url}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Antigravity/4.0.6",
        }

        try:
            response = s.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "data" in data:
                    return self._merge_models(data["data"])
                if isinstance(data, list):
                    return self._merge_models(data)
                return self._merge_models([])

            print(f"[-] API Error {response.status_code}: {response.text}")
            return self._merge_models([])
        except Exception as e:
            print(f"[-] Models Request failed: {e}", file=sys.stderr)
            return self._merge_models([])
