# Gemini Web-to-API Skill

这个 skill 通过 Quicker 动作把 Gemini 网页版能力转换为本地 OpenAI 兼容接口。

当前版本的策略是：
- 文本任务优先使用 `gemini-3.1-pro-preview`
- 轻量任务可使用 `gemini-3.1-flash-lite-preview`
- 生图任务优先使用 `gemini-3.1-flash-image-preview`
- 当 Quicker 动作的模型列表落后时，客户端会自动补充常用 `3.1` 模型名
- 当优先模型不可用时，客户端会自动回退到兼容的 `3.0` 模型

## 依赖

1. 安装 Quicker
2. 安装并启动动作：
   `https://getquicker.net/Sharedaction?code=54037596-7003-47cb-dca5-08de3bb54158`
3. 确认本地服务地址可访问：
   `http://127.0.0.1:55557/v1`

## 目录结构

- `libs/`：本地 API 客户端封装
- `scripts/`：对话、生图、模型查询脚本
- `resources/`：比例参考图等资源

## 推荐模型

### 文本
- `gemini-3.1-pro-preview`
- `gemini-3.1-flash-lite-preview`

### 图片
- `gemini-3.1-flash-image-preview`

### 兼容回退
- `gemini-3-pro`
- `gemini-3-flash`
- `gemini-3-pro-image`
- `gemini-3-image`
- `gemini-3-flash-image`

## 使用示例

### 查看模型
```bash
python scripts/list_models.py
```

### 文本对话
```bash
python scripts/chat.py "请总结这段代码的风险"
```

### 指定模型
```bash
python scripts/chat.py "请只回复 ok" "gemini-3.1-pro-preview"
```

### 生成图片
```bash
python scripts/generate_image.py "雨夜霓虹灯下的橘猫，电影感，高细节" "1:1"
```

## 说明

- `/models` 如果只返回旧的 `gemini-3-*` 列表，不代表 `3.1` 一定不可用
- 这个客户端会优先按 `3.1` 模型名发起请求
- 如果远端返回模型不可用或服务繁忙，会自动尝试兼容回退

## 排查

### 连接失败
- 确认 Quicker 动作已经启动
- 确认端口与 `config.json` 一致

### 登录态失效
- 检查 Gemini 网页是否要求重新登录或验证码验证

### 生图失败
- 优先确认 Quicker 动作是否已经支持对应图片模型名
- 如不支持，客户端会尝试回退到旧图片模型
