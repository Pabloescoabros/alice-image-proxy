# Alice Yandex Proxy / Прокси Яндекс Алисы

**OpenAI-compatible API proxy for Yandex Alice** — wraps Alice into a standard API format with multiple models through a single endpoint.

**OpenAI-совместимый прокси-сервер для Яндекс Алисы** — оборачивает Алису в стандартный API формат с несколькими моделями через единую точку входа.

---

## 🌐 Languages / Языки

- [English](#english)
- [Русский](#русский)

---

# English

## Models

| Model | Description |
|-------|-------------|
| `alice` | Base chat |
| `alice-pro` | Advanced chat powered by YandexGPT 5 Pro |
| `alice-search` | Deep research agent with internet access |
| `alice-image` | Image generation |
| `alice-vision` | Image analysis and description |
| `alice-code` | Programming and coding tasks |

## Features

- Full OpenAI API compatibility (`/v1/chat/completions`, `/v1/images/generations`, `/v1/images/edits`, `/v1/vision/analyze`)
- **Multi-session management** — separate Alice chat per model type with automatic rotation and context summarization
- **Project system** — isolate sessions by project name, each project gets its own set of model sessions
- **Unified media endpoint** — generate, edit, and analyze images in a single shared chat session for context continuity
- **Auto prompt enhancement** — Russian prompts are automatically translated and enriched with quality-boosting keywords for image generation
- **Streaming responses** — SSE-compatible streaming for chat completions
- **Smart model detection** — automatically routes requests to the optimal model based on message content
- **File management API** — read, write, and list files remotely
- **Remote command execution** — run shell commands via API
- **Free** — no API keys, no subscriptions, just a Yandex account

## Requirements

- Python 3.10+
- Google Chrome (installed on the system)
- Yandex account
- Dependencies: `fastapi`, `uvicorn`, `playwright`, `httpx`, `pydantic`

## Installation

### Quick Start (recommended)

The project includes an automatic setup checker that verifies all prerequisites and installs missing dependencies:

```bash
# Clone
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# Run setup checker — installs everything that's missing
python setup.py
```

The setup script checks:
- Python version (3.10+)
- pip availability
- Required packages (fastapi, uvicorn, playwright, httpx, pydantic)
- Google Chrome / Chromium browser
- Playwright browser binaries
- Port availability (default 8976)
- Project structure (required files and directories)

Use `--check` to verify without installing:

```bash
python setup.py --check
```

### Manual Installation

<details>
<summary>Windows</summary>

```powershell
# 1. Install Python 3.10+ (if not installed)
winget install Python.Python.3.13

# 2. Clone the repo
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. Install Python dependencies
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 4. Install Playwright browser
python -m playwright install chromium

# 5. Install Chrome (if not installed)
winget install Google.Chrome
```

</details>

<details>
<summary>Linux (Debian/Ubuntu)</summary>

```bash
# 1. Install Python 3.10+ and pip
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# 2. Clone the repo
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. (Optional) Create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 4. Install Python dependencies
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 5. Install Playwright browser and system dependencies
python -m playwright install chromium
python -m playwright install-deps chromium

# 6. Install Google Chrome (if not installed)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main' | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update && sudo apt install -y google-chrome-stable
```

</details>

<details>
<summary>Linux (Fedora/RHEL)</summary>

```bash
# 1. Install Python and pip
sudo dnf install -y python3 python3-pip git

# 2. Clone the repo
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. Install Python dependencies
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 4. Install Playwright browser and system dependencies
python -m playwright install chromium
python -m playwright install-deps chromium

# 5. Install Chrome (optional, Chromium from repo works too)
sudo dnf install -y fedora-workstation-repositories
sudo dnf config-manager --set-enabled google-chrome
sudo dnf install -y google-chrome-stable
```

</details>

<details>
<summary>Linux (Arch)</summary>

```bash
# 1. Install dependencies
sudo pacman -S python python-pip git chromium

# 2. Clone the repo
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. Install Python dependencies
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 4. Install Playwright browser
python -m playwright install chromium
```

</details>

<details>
<summary>macOS</summary>

```bash
# 1. Install Python (if needed)
brew install python@3.13

# 2. Clone the repo
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. Install Python dependencies
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 4. Install Playwright browser
python -m playwright install chromium

# 5. Install Chrome (if not installed)
brew install --cask google-chrome
```

</details>

## Quick Start

```bash
python server.py
```

Server starts on `http://localhost:8976` (configurable via `PORT` env var).

### Authentication

On first launch, Chrome opens automatically — log into your Yandex account manually. Cookies are saved for subsequent runs.

Alternatively, set cookies via API:

```bash
curl -X POST http://localhost:8976/cookies \
  -H "Content-Type: application/json" \
  -d '{"cookie": "your_cookie_string_here"}'
```

Check authentication status:

```bash
curl http://localhost:8976/cookies/status
```

## API Reference

### Chat Completions

```bash
curl -X POST http://localhost:8976/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "alice",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false,
    "project": "default"
  }'
```

The `project` field isolates sessions — different projects get separate Alice chats per model. If the model is not specified, the proxy auto-detects the optimal model based on message content.

### Image Generation

```bash
curl -X POST http://localhost:8976/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "cat at sunset, oil painting",
    "model": "alice-image",
    "n": 1,
    "response_format": "url"
  }'
```

`response_format`: `"url"` returns image URL, `"b64_json"` returns base64-encoded image.

### Image Editing

Two methods available:

**Method 1 — Upload** (reliable): upload an image and describe changes.

```bash
curl -X POST http://localhost:8976/v1/images/edits \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "make the background darker",
    "image_url": "https://example.com/image.jpg",
    "method": "upload"
  }'
```

**Method 2 — Button** (generate then edit): generates an image first, then edits via Alice's built-in edit button.

```bash
curl -X POST http://localhost:8976/v1/images/edits \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "add a hat to the cat",
    "gen_prompt": "cute cat sitting on a windowsill",
    "method": "button"
  }'
```

### Vision / Image Analysis

```bash
curl -X POST http://localhost:8976/v1/vision/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/image.jpg",
    "prompt": "Describe what you see in detail"
  }'
```

Accepts `image` (base64) or `url`.

### Unified Media Endpoint

All media operations in one shared chat session for context continuity:

```bash
# Generate
curl -X POST http://localhost:8976/v1/media/generate \
  -H "Content-Type: application/json" \
  -d '{"action": "generate", "prompt": "mountain landscape"}'

# Edit last generated image via button
curl -X POST http://localhost:8976/v1/media/generate \
  -H "Content-Type: application/json" \
  -d '{"action": "edit_button", "edit_prompt": "make it snowy"}'

# Edit via upload
curl -X POST http://localhost:8976/v1/media/generate \
  -H "Content-Type: application/json" \
  -d '{"action": "edit_upload", "edit_prompt": "add clouds", "url": "https://..."}'

# Analyze image in the same session
curl -X POST http://localhost:8976/v1/media/generate \
  -H "Content-Type: application/json" \
  -d '{"action": "vision", "url": "https://...", "prompt": "What colors dominate?"}'
```

### Media File Management

```bash
# List saved media files
curl http://localhost:8976/v1/media/list

# Delete a media file
curl -X DELETE http://localhost:8976/v1/media/filename.jpg
```

### Projects

```bash
# List all projects
curl http://localhost:8976/v1/projects

# Create a project
curl -X POST http://localhost:8976/v1/projects/my-project \
  -H "Content-Type: application/json" \
  -d '{"description": "My AI project"}'

# Create sessions for a project
curl -X POST http://localhost:8976/v1/projects/my-project/sessions \
  -H "Content-Type: application/json" \
  -d '{"models": ["alice", "alice-code", "alice-image"]}'

# Delete a project (closes all its sessions)
curl -X DELETE http://localhost:8976/v1/projects/my-project
```

### Sessions

```bash
# List active sessions
curl http://localhost:8976/v1/sessions

# Force-rotate a session (summarize and start fresh)
curl -X POST http://localhost:8976/v1/sessions/default:alice/rotate
```

### File Operations

```bash
# Write file
curl -X POST http://localhost:8976/v1/files/write \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/test.txt", "content": "hello"}'

# Read file
curl -X POST http://localhost:8976/v1/files/read \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/test.txt"}'

# List files
curl -X POST http://localhost:8976/v1/files/list \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp", "pattern": "*.txt"}'
```

### Remote Execution

```bash
curl -X POST http://localhost:8976/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "echo hello", "timeout": 10}'
```

### Health & Debug

```bash
curl http://localhost:8976/health    # server status, browser state, sessions
curl http://localhost:8976/debug     # detailed debug info with screenshot path
curl http://localhost:8976/v1/models # list available models
```

## Client Integration

Works with any software supporting the OpenAI API format:

- **Cursor** — set API base to `http://localhost:8976/v1`
- **Hermes Agent** — add as a custom provider
- **Open WebUI** — connect as an OpenAI endpoint
- **Any HTTP client** — standard REST endpoints

## Architecture

```
┌─────────────────┐     OpenAI API      ┌──────────────────┐    Playwright CDP    ┌─────────────────┐
│   Your Client   │ ──────────────────▶  │  Alice Proxy     │ ──────────────────▶  │  Chrome/Alice   │
│ (Cursor, CLI,   │ ◀──────────────────  │  (FastAPI:8976)  │ ◀──────────────────  │  (alice.yandex) │
│  WebUI, etc.)   │     JSON/SSE         │                  │    DOM interaction   │                 │
└─────────────────┘                      └──────────────────┘                      └─────────────────┘
```

The proxy launches Chrome with remote debugging, connects via CDP (Chrome DevTools Protocol) using Playwright, and interacts with alice.yandex.ru through DOM manipulation. Each model type gets its own isolated browser tab and Alice chat session. Sessions auto-rotate after 50 messages with context summarization.

## Notes

- Tested only via direct API requests. CLI/IDE/GUI client integration not fully validated — your mileage may vary
- Active development — API may change between versions
- Image generation uses Alice's internal model; prompts are auto-translated and enhanced
- Session rotation happens automatically at 50 messages — the current chat is summarized, deleted, and a new one starts with the summary as context

## License

MIT

---

# Русский

## Модели

| Модель | Описание |
|--------|----------|
| `alice` | Базовый чат |
| `alice-pro` | Продвинутый чат на YandexGPT 5 Pro |
| `alice-search` | Агент глубокого ресёрча с доступом в интернет |
| `alice-image` | Генерация изображений |
| `alice-vision` | Анализ и описание изображений |
| `alice-code` | Задачи программирования |

## Возможности

- Полная совместимость с OpenAI API (`/v1/chat/completions`, `/v1/images/generations`, `/v1/images/edits`, `/v1/vision/analyze`)
- **Мульти-сессия** — отдельный чат Алисы для каждого типа модели с автоматической ротацией и суммаризацией контекста
- **Система проектов** — изоляция сессий по имени проекта, каждый проект получает свой набор сессий моделей
- **Единый медиа-эндпоинт** — генерация, редактирование и анализ изображений в одной общей чат-сессии для сохранения контекста
- **Автоэнхансмент промптов** — русские промпты автоматически переводятся и обогащаются ключевыми словами для качественной генерации
- **Стриминг ответов** — SSE-совместимый стриминг для чат-комплишенов
- **Умное определение модели** — автоматическая маршрутизация запросов к оптимальной модели на основе содержимого сообщения
- **Файловый API** — чтение, запись и список файлов удалённо
- **Удалённое выполнение команд** — запуск shell-команд через API
- **Бесплатно** — никаких API-ключей и подписок, нужен только аккаунт Яндекса

## Требования

- Python 3.10+
- Google Chrome (установлен в системе)
- Аккаунт Яндекса
- Зависимости: `fastapi`, `uvicorn`, `playwright`, `httpx`, `pydantic`

## Установка

### Быстрый старт (рекомендуется)

В проект включён автоматический чекер установки — проверяет все зависимости и устанавливает недостающее:

```bash
# Клонировать
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# Запустить чекер — установит всё что нужно
python setup.py
```

Скрипт проверяет:
- Версию Python (3.10+)
- Наличие pip
- Python-пакеты (fastapi, uvicorn, playwright, httpx, pydantic)
- Браузер Google Chrome / Chromium
- Браузер Playwright (бинарники)
- Доступность порта (по умолчанию 8976)
- Структуру проекта (файлы и директории)

Только проверка без установки:

```bash
python setup.py --check
```

### Ручная установка

<details>
<summary>Windows</summary>

```powershell
# 1. Установить Python 3.10+ (если не установлен)
winget install Python.Python.3.13

# 2. Клонировать репозиторий
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. Установить Python-зависимости
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 4. Установить браузер Playwright
python -m playwright install chromium

# 5. Установить Chrome (если не установлен)
winget install Google.Chrome
```

</details>

<details>
<summary>Linux (Debian/Ubuntu)</summary>

```bash
# 1. Установить Python 3.10+ и pip
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# 2. Клонировать репозиторий
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. (Опционально) Создать виртуальное окружение
python3 -m venv .venv && source .venv/bin/activate

# 4. Установить Python-зависимости
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 5. Установить браузер Playwright и системные зависимости
python -m playwright install chromium
python -m playwright install-deps chromium

# 6. Установить Google Chrome (если не установлен)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main' | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update && sudo apt install -y google-chrome-stable
```

</details>

<details>
<summary>Linux (Fedora/RHEL)</summary>

```bash
# 1. Установить Python и pip
sudo dnf install -y python3 python3-pip git

# 2. Клонировать репозиторий
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. Установить Python-зависимости
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 4. Установить браузер Playwright и системные зависимости
python -m playwright install chromium
python -m playwright install-deps chromium

# 5. Установить Chrome (опционально, Chromium из репо тоже подойдёт)
sudo dnf install -y fedora-workstation-repositories
sudo dnf config-manager --set-enabled google-chrome
sudo dnf install -y google-chrome-stable
```

</details>

<details>
<summary>Linux (Arch)</summary>

```bash
# 1. Установить зависимости
sudo pacman -S python python-pip git chromium

# 2. Клонировать репозиторий
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. Установить Python-зависимости
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 4. Установить браузер Playwright
python -m playwright install chromium
```

</details>

<details>
<summary>macOS</summary>

```bash
# 1. Установить Python (если нужен)
brew install python@3.13

# 2. Клонировать репозиторий
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# 3. Установить Python-зависимости
pip install fastapi uvicorn[standard] playwright httpx pydantic

# 4. Установить браузер Playwright
python -m playwright install chromium

# 5. Установить Chrome (если не установлен)
brew install --cask google-chrome
```

</details>

## Быстрый старт

```bash
python server.py
```

Сервер запустится на `http://localhost:8976` (настраивается через переменную окружения `PORT`).

### Авторизация

При первом запуске Chrome откроется автоматически — войдите в аккаунт Яндекса вручную. Cookies сохраняются для последующих запусков.

Также можно установить cookies через API:

```bash
curl -X POST http://localhost:8976/cookies \
  -H "Content-Type: application/json" \
  -d '{"cookie": "ваша_cookie_строка"}'
```

Проверка статуса авторизации:

```bash
curl http://localhost:8976/cookies/status
```

## Справочник API

### Чат-комплишены

```bash
curl -X POST http://localhost:8976/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "alice",
    "messages": [{"role": "user", "content": "Привет"}],
    "stream": false,
    "project": "default"
  }'
```

Поле `project` изолирует сессии — разные проекты получают отдельные чаты Алисы для каждой модели. Если модель не указана, прокси автоматически определяет оптимальную модель по содержимому сообщения.

### Генерация изображений

```bash
curl -X POST http://localhost:8976/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "кот на закате, масляная живопись",
    "model": "alice-image",
    "n": 1,
    "response_format": "url"
  }'
```

`response_format`: `"url"` возвращает URL картинки, `"b64_json"` — base64-кодированное изображение.

### Редактирование изображений

Два метода:

**Метод 1 — Upload** (надёжный): загрузить изображение и описать изменения.

```bash
curl -X POST http://localhost:8976/v1/images/edits \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "сделай фон темнее",
    "image_url": "https://example.com/image.jpg",
    "method": "upload"
  }'
```

**Метод 2 — Button** (генерация + редактирование): сначала генерирует изображение, затем редактирует через встроенную кнопку Алисы.

```bash
curl -X POST http://localhost:8976/v1/images/edits \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "добавь коту шляпу",
    "gen_prompt": "милый кот сидит на подоконнике",
    "method": "button"
  }'
```

### Зрение / Анализ изображений

```bash
curl -X POST http://localhost:8976/v1/vision/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/image.jpg",
    "prompt": "Опиши что видишь подробно"
  }'
```

Принимает `image` (base64) или `url`.

### Единый медиа-эндпоинт

Все операции с медиа в одной общей чат-сессии для сохранения контекста:

```bash
# Генерация
curl -X POST http://localhost:8976/v1/media/generate \
  -H "Content-Type: application/json" \
  -d '{"action": "generate", "prompt": "горный пейзаж"}'

# Редактирование последнего изображения через кнопку
curl -X POST http://localhost:8976/v1/media/generate \
  -H "Content-Type: application/json" \
  -d '{"action": "edit_button", "edit_prompt": "сделай зимним"}'

# Редактирование через загрузку
curl -X POST http://localhost:8976/v1/media/generate \
  -H "Content-Type: application/json" \
  -d '{"action": "edit_upload", "edit_prompt": "добавь облака", "url": "https://..."}'

# Анализ изображения в той же сессии
curl -X POST http://localhost:8976/v1/media/generate \
  -H "Content-Type: application/json" \
  -d '{"action": "vision", "url": "https://...", "prompt": "Какие цвета преобладают?"}'
```

### Управление медиа-файлами

```bash
# Список сохранённых медиа-файлов
curl http://localhost:8976/v1/media/list

# Удалить медиа-файл
curl -X DELETE http://localhost:8976/v1/media/filename.jpg
```

### Проекты

```bash
# Список всех проектов
curl http://localhost:8976/v1/projects

# Создать проект
curl -X POST http://localhost:8976/v1/projects/my-project \
  -H "Content-Type: application/json" \
  -d '{"description": "Мой AI проект"}'

# Создать сессии для проекта
curl -X POST http://localhost:8976/v1/projects/my-project/sessions \
  -H "Content-Type: application/json" \
  -d '{"models": ["alice", "alice-code", "alice-image"]}'

# Удалить проект (закрывает все его сессии)
curl -X DELETE http://localhost:8976/v1/projects/my-project
```

### Сессии

```bash
# Список активных сессий
curl http://localhost:8976/v1/sessions

# Принудительная ротация сессии (суммаризация и начало заново)
curl -X POST http://localhost:8976/v1/sessions/default:alice/rotate
```

### Файловые операции

```bash
# Записать файл
curl -X POST http://localhost:8976/v1/files/write \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/test.txt", "content": "привет"}'

# Прочитать файл
curl -X POST http://localhost:8976/v1/files/read \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp/test.txt"}'

# Список файлов
curl -X POST http://localhost:8976/v1/files/list \
  -H "Content-Type: application/json" \
  -d '{"path": "/tmp", "pattern": "*.txt"}'
```

### Удалённое выполнение

```bash
curl -X POST http://localhost:8976/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "echo hello", "timeout": 10}'
```

### Здоровье и отладка

```bash
curl http://localhost:8976/health    # статус сервера, состояние браузера, сессии
curl http://localhost:8976/debug     # детальная отладка с путём к скриншоту
curl http://localhost:8976/v1/models # список доступных моделей
```

## Подключение к клиентам

Работает с любым софтом, поддерживающим OpenAI API формат:

- **Cursor** — в настройках API укажите `http://localhost:8976/v1`
- **Hermes Agent** — добавьте как кастомный провайдер
- **Open WebUI** — подключите как OpenAI endpoint
- **Любой HTTP-клиент** — стандартные REST-эндпоинты

## Архитектура

```
┌─────────────────┐     OpenAI API      ┌──────────────────┐    Playwright CDP    ┌─────────────────┐
│   Ваш клиент    │ ──────────────────▶  │  Alice Proxy     │ ──────────────────▶  │  Chrome/Alice   │
│ (Cursor, CLI,   │ ◀──────────────────  │  (FastAPI:8976)  │ ◀──────────────────  │  (alice.yandex) │
│  WebUI и т.д.)  │     JSON/SSE         │                  │    DOM-взаимодействие│                 │
└─────────────────┘                      └──────────────────┘                      └─────────────────┘
```

Прокси запускает Chrome с удалённой отладкой, подключается через CDP (Chrome DevTools Protocol) с помощью Playwright и взаимодействует с alice.yandex.ru через DOM-манипуляции. Каждый тип модели получает свою изолированную вкладку браузера и чат-сессию Алисы. Сессии автоматически ротируются после 50 сообщений с суммаризацией контекста.

## Примечания

- Тестировалось только через прямые запросы к API. Интеграция с CLI/IDE/GUI клиентами полностью не валидирована — могут быть нюансы
- Активная разработка — API может меняться между версиями
- Генерация изображений использует внутреннюю модель Алисы; промпты автоматически переводятся и улучшаются
- Ротация сессий происходит автоматически на 50 сообщениях — текущий чат суммаризируется, удаляется, и начинается новый с кратким описанием предыдущего контекста

## Лицензия

MIT
