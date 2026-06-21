# Alice Image Proxy

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

OpenAI-compatible API proxy for Yandex Alice with multi-model support, image generation, editing, and vision capabilities.

## Features

- **6 Virtual Models**: alice, alice-pro, alice-search, alice-image, alice-vision, alice-code
- **Image Generation**: High-quality image generation via Alice's "Нарисуй" command
- **Image Editing**: Two methods — upload + edit prompt, or UI "Изменить" button
- **Vision Analysis**: Upload images for Alice to analyze and describe
- **Session Management**: Automatic session rotation with summarization for context continuity
- **OpenAI-Compatible API**: Drop-in replacement for OpenAI SDK clients

## Architecture

```
┌─────────────┐
│  FastAPI    │  Port 8976
│  Server     │
└──────┬──────┘
       │
       ├─► AliceRPC (HTTP client to rpc.alice.yandex.ru)
       │
       └─► AliceBrowser (Playwright + Chrome CDP)
            ├─► alice.yandex.ru (base chat)
            ├─► alice.yandex.ru/?model=pro (pro)
            ├─► alice.yandex.ru/?draw_picture=1 (image gen)
            └─► alice.yandex.ru/?model=alice-agents-deep-research (search)
```

## Requirements

- Python 3.11+
- Google Chrome (for CDP connection)
- Yandex account with Alice access

## Installation

```bash
# Clone repository
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# Install dependencies
pip install fastapi uvicorn playwright httpx pydantic

# Install Playwright browsers
playwright install chromium
```

## Configuration

1. **Login to Alice**: Start the server and open Chrome with remote debugging:
   ```bash
   python server.py
   ```

2. **Manual Login**: If not authenticated, Chrome will open for manual login (180s timeout)

3. **Cookie Injection**: Alternatively, set cookies via API:
   ```bash
   curl -X POST http://localhost:8976/cookies \
     -H "Content-Type: application/json" \
     -d '{"cookie": "your_cookie_string_here"}'
   ```

## Usage

### Start Server

```bash
python server.py
# or with custom port
PORT=8080 python server.py
```

### Chat Completions

```bash
curl http://localhost:8976/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "alice",
    "messages": [{"role": "user", "content": "Привет! Как дела?"}],
    "stream": false
  }'
```

### Image Generation

```bash
curl http://localhost:8976/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a beautiful sunset over the ocean",
    "n": 1,
    "size": "1024x1024",
    "response_format": "url"
  }'
```

### Image Editing (Method 1: Upload + Edit)

```bash
curl http://localhost:8976/v1/images/edits \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "make the sky purple and add clouds",
    "url": "https://example.com/image.jpg",
    "model": "alice-pro",
    "method": "upload"
  }'
```

### Image Editing (Method 2: Generate + Edit Button)

```bash
curl http://localhost:8976/v1/images/edits \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "add a rainbow in the background",
    "gen_prompt": "a cute fox in a meadow",
    "model": "alice-image",
    "method": "button"
  }'
```

### Vision Analysis

```bash
curl http://localhost:8976/v1/vision/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/image.jpg",
    "prompt": "Describe this image in detail"
  }'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions with auto-model detection |
| `/v1/images/generations` | POST | Generate images |
| `/v1/images/edits` | POST | Edit images (upload or button method) |
| `/v1/vision/analyze` | POST | Analyze images |
| `/v1/models` | GET/POST | List available models |
| `/v1/sessions` | GET | List active sessions |
| `/v1/sessions/{model}/rotate` | POST | Force session rotation |
| `/health` | GET | Health check |
| `/debug` | GET | Debug info with screenshot |
| `/cookies` | POST | Set authentication cookies |
| `/cookies/status` | GET | Check cookie status |

## Model Descriptions

- **alice**: Base chat model
- **alice-pro**: Advanced chat with YandexGPT 5 Pro
- **alice-search**: Deep research agent with web search
- **alice-image**: Image generation via "Нарисуй" command
- **alice-vision**: Image analysis and description
- **alice-code**: Optimized for coding tasks

## Session Management

Sessions automatically rotate after 50 messages:
1. Alice summarizes the conversation
2. Old chat is deleted from sidebar
3. New chat starts with summary as context
4. Continuity is preserved across rotations

## Prompt Enhancement

Image prompts are automatically enhanced:
- Russian → English translation (40+ common terms)
- Quality boosters: "8K resolution", "ultra-detailed", "cinematic lighting"
- Style enhancers: "masterpiece", "trending on ArtStation", "professional photography"

## Security Notes

⚠️ **Warning**: The following endpoints provide unrestricted access and should be protected in production:
- `/v1/execute` — Execute shell commands
- `/v1/files/*` — Read/write files on the server

Consider adding authentication middleware or restricting access to trusted networks.

## Troubleshooting

### Login Issues
- Check cookie validity: `curl http://localhost:8976/cookies/status`
- Re-authenticate via `/cookies` endpoint or manual Chrome login

### Image Generation Fails
- Verify Alice is logged in and has image generation access
- Check logs: `tail -f alice_proxy.log`

### Session Rotation Issues
- Force rotation: `curl -X POST http://localhost:8976/v1/sessions/alice/rotate`
- Check sidebar visibility in debug screenshot: `curl http://localhost:8976/debug`

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions welcome! Please open an issue or pull request.

## Disclaimer

This project is not affiliated with or endorsed by Yandex. Use at your own risk.
