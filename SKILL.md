---
name: gemini-web-quicker-skill
description: 当用户需要使用 Gemini API 服务（通过 Quicker 动作提供：gemini-thinking, gemini-3-flash/pro, gemini-3-image、banana香蕉生图、视频分析理解）时使用此技能。
---

# Gemini Web-to-API (Quicker) Skill

## 目标
利用由 Quicker 动作转接的 Gemini 网页版 API，提供包括 **Gemini Thinking (3.0 Thinking)**、**Gemini 3 Flash/Pro** 以及 **Imagen 3 (Gemini 3 Image)** 的高级能力。

## 场景
- **深度推理**: 使用 `gemini-thinking` 进行复杂逻辑分析。
- **极速对话**: 使用 `gemini-3-flash` 处理日常任务和视频理解。
- **高清绘图**: 使用 `gemini-3-image` 或 `gemini-3-pro-image` 生成高质量素材。
- **视频深度理解**: 支持大视频自动压缩上传并分析。

## 环境配置 (Setup)

### ⚠️ 核心依赖：Quicker 动作
本技能**必须**配合特定的 Quicker 动作运行。请按以下步骤配置：

1.  **安装 Quicker**: 如果尚未安装，请前往 [getquicker.net](https://getquicker.net/) 下载安装并登录。
2.  **安装专用动作**: 复制并安装此动作：[Gemini 网页转 API 提供服务](https://getquicker.net/Sharedaction?code=54037596-7003-47cb-dca5-08de3bb54158)。
3.  **启动服务**: 在 Quicker 中启动该动作。动作会开启一个本地 HTTP 服务（通常端口为 `55557`）。
4.  **安装 FFmpeg (推荐)**: 当视频超过一定大小（100m）时，视频分析依赖它进行压缩。

### 验证连接
运行指令 "查看所有模型" 或 "确认 gemini-web-quicker 配置好了吗" 来测试。

## 模型列表
- `gemini-web-api` (基础服务)
- `gemini-thinking` (强逻辑推理)
- `gemini-3-flash` (快节奏、多模态)
- `gemini-3-pro` (高精度)
- `gemini-3-image` (标准生图)
- `gemini-3-flash-image` (快速生图)
- `gemini-3-pro-image` (精品生图)

## 指令建议

### 🗣️ 试试这样问 AI
- **逻辑分析**: "请用 gemini模型 帮我分析这段代码的潜在漏洞。"
- **快速对话**: "请用 gemini-3-flash 帮我写一个短视频脚本。"
- **高质量生图**: "用 gemini-3-pro-image 生成一张 16:9 的赛博朋克城市背景图。"
- **视频理解**: "帮我分析下这个视频的内容：[视频路径]"
- **查看模型**: "查看现在有哪些模型可以用。"

## 脚本说明

### 1. 通用对话 (Chat)
- **执行**: `python scripts/chat.py "{Prompt}" "{ModelName}" "{FilePath}"`
- **能力**: 自动处理视频压缩（>100MB）并发送至 Web API。

### 2. 高清绘图 (Image Generation)
- **执行**: `python scripts/generate_image.py "{Prompt}" "{Size/Ratio}"`
- **默认模型**: `gemini-3-flash-image`

### 3. 查看可用模型
- **执行**: `python scripts/list_models.py`

## 注意事项
- 确保 Quicker 动作处于运行状态。
- 如果请求超时，请检查网页端 Gemini 是否需要手动验证或已掉线。
- 图片保存在 `generated_assets/`。
