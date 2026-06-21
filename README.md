# Alice Yandex Proxy

OpenAI-совместимый прокси-сервер для Яндекс Алисы. Оборачивает Алису в стандартный API формат, позволяет использовать несколько моделей через единую точку входа.

## Модели

- `alice` — базовый чат
- `alice-pro` — продвинутый чат на YandexGPT 5 Pro
- `alice-search` — агент глубокого ресёрча с доступом в интернет
- `alice-image` — генерация изображений
- `alice-vision` — анализ изображений
- `alice-code` — задачи программирования

## Возможности

- Полная совместимость с OpenAI API (`/v1/chat/completions`, `/v1/images/generations`, `/v1/images/edits`, `/v1/vision/analyze`)
- Автоматическая ротация сессий с суммаризацией контекста
- Автоэнхансмент промптов для генерации изображений
- Мульти-сессия — отдельный чат Алисы для каждого типа модели
- Управление через API (сессии, файлы, команды)
- Streaming responses
- **Бесплатно** — нужен только аккаунт Яндекса

## Установка

```bash
# Клонировать
git clone https://github.com/Pabloescoabros/alice-image-proxy.git
cd alice-image-proxy

# Установить зависимости
pip install fastapi uvicorn playwright httpx pydantic

# Установить браузер
playwright install chromium
```

## Запуск

```bash
python server.py
```

Сервер запустится на `http://localhost:8976`

## Использование

### Авторизация

Первый запуск потребует авторизации в Яндекс. Браузер откроется автоматически — войдите в аккаунт вручную. Cookies сохранятся для последующих запусков.

Также можно установить cookies через API:

```bash
curl -X POST http://localhost:8976/cookies \
  -H "Content-Type: application/json" \
  -d '{"cookie": "your_cookie_string_here"}'
```

### Chat Completions

```bash
curl -X POST http://localhost:8976/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "alice",
    "messages": [{"role": "user", "content": "Привет"}]
  }'
```

### Генерация изображений

```bash
curl -X POST http://localhost:8976/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "кот на закате",
    "model": "alice-image",
    "n": 1
  }'
```

### Анализ изображений (Vision)

```bash
curl -X POST http://localhost:8976/v1/vision/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/image.jpg",
    "prompt": "Опиши что видишь"
  }'
```

### Проверка здоровья

```bash
curl http://localhost:8976/health
```

## Подключение к клиентам

Работает с любым софтом поддерживающим OpenAI API формат:

- **Cursor** — в настройках API укажите `http://localhost:8976/v1`
- **Hermes Agent** — добавьте как кастомный провайдер
- **Open WebUI** — подключите как OpenAI endpoint
- **Любой HTTP-клиент** — стандартные эндпоинты

## API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/v1/chat/completions` | POST | Чат с моделями |
| `/v1/images/generations` | POST | Генерация картинок |
| `/v1/images/edits` | POST | Редактирование картинок |
| `/v1/vision/analyze` | POST | Анализ изображений |
| `/v1/models` | GET | Список моделей |
| `/v1/sessions` | GET | Активные сессии |
| `/v1/sessions/{model}/rotate` | POST | Ротация сессии |
| `/health` | GET | Статус сервера |
| `/cookies` | POST | Установить cookies |

## Требования

- Python 3.10+
- Google Chrome (установлен в системе)
- Аккаунт Яндекса

## Примечания

- Тестировалось только через прямые запросы к API. В CLI/IDE/GUI клиентах не обкатывалось — могут быть нюансы
- Проект в активной разработке, API может меняться
- Для генерации изображений Алиса использует свою внутреннюю модель, промпты автоматически переводятся и улучшаются

## Лицензия

MIT
