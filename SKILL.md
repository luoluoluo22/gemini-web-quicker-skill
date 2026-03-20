---
name: gemini-web-quicker-skill
description: 当用户需要通过 Quicker 本地动作调用 Gemini 网页能力时使用，支持 `gemini-3.1-*` 文本与生图模型，以及视频理解等场景。
---

# Gemini Web-to-API (Quicker) Skill

## 目标
通过 Quicker 动作把 Gemini 网页版能力暴露为本地 OpenAI 兼容接口，优先使用 Gemini 3.1 系列模型。

## 适用场景
- 深度推理：优先使用 `gemini-3.1-pro-preview`
- 快速对话：可使用 `gemini-3.1-flash-lite-preview`
- 图片生成：优先使用 `gemini-3.1-flash-image-preview`
- 视频理解：通过 `scripts/chat.py` 传入本地媒体文件

## 环境配置

### 核心依赖：Quicker 动作
本技能依赖 Quicker 的本地服务动作：
`Gemini 网页转 API 提供服务`

配置步骤：
1. 安装 Quicker，并确保可以正常运行。
2. 安装动作：
   `https://getquicker.net/Sharedaction?code=54037596-7003-47cb-dca5-08de3bb54158`
3. 在 Quicker 中启动该动作。
4. 确认本地服务可访问，默认地址通常为 `http://127.0.0.1:55557/v1`

### 推荐验证方式
- 查看模型：`python scripts/list_models.py`
- 文本测试：`python scripts/chat.py "请只回复 ok"`
- 生图测试：`python scripts/generate_image.py "一只雨夜街头的橘猫" "1:1"`

## 推荐模型
- `gemini-3.1-pro-preview`
- `gemini-3.1-flash-lite-preview`
- `gemini-3.1-flash-image-preview`

## 兼容模型
- `gemini-3-pro`
- `gemini-3-flash`
- `gemini-3-pro-image`
- `gemini-3-image`
- `gemini-3-flash-image`
- `gemini-thinking`
- `gemini-web-api`

## 脚本说明

### 1. 文本对话
`python scripts/chat.py "{Prompt}" "{ModelName}" "{FilePath}"`

默认优先模型：
- 文本：`gemini-3.1-pro-preview`
- 如果不可用，会自动回退到较旧模型

### 2. 图片生成
`python scripts/generate_image.py "{Prompt}" "{Size/Ratio}"`

默认优先模型：
- 图片：`gemini-3.1-flash-image-preview`
- 如果不可用，会自动回退到 `gemini-3-pro-image` 等模型

### 3. 查看模型
`python scripts/list_models.py`

说明：
- 即使 Quicker 动作返回的 `/models` 列表较旧，客户端也会补充本地推荐的 3.1 模型名

## 注意事项
- 确保 Quicker 动作处于运行状态
- 如果请求超时，先检查 Gemini 网页登录态是否失效
- 生成图片默认保存在 `generated_assets/`
