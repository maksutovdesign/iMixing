from __future__ import annotations

import json
import os
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .midi_fixer import MidiFixOptions, fix_midi_bytes, list_style_names


API_TIMEOUT_SECONDS = 70


@dataclass
class ChatPreferences:
    style: str = "balanced"
    output_format: int = 1


def normalize_style(style: str) -> str:
    key = (style or "").strip().lower()
    if key not in list_style_names():
        allowed = ", ".join(list_style_names())
        raise ValueError(f"Unknown style. Use one of: {allowed}.")
    return key


def api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def file_url(token: str, file_path: str) -> str:
    return f"https://api.telegram.org/file/bot{token}/{file_path}"


def telegram_request_json(token: str, method: str, payload: dict | None = None) -> dict | list:
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        api_url(token, method),
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"Telegram HTTP error {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Telegram network error: {error.reason}") from error

    if not parsed.get("ok"):
        raise RuntimeError(parsed.get("description", f"Telegram API call failed: {method}"))
    return parsed["result"]


def encode_multipart(
    *,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----iMixingBoundary{uuid.uuid4().hex}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for name, (filename, file_bytes, mime_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
            ).encode("utf-8")
        )
        body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_bytes)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), boundary


def telegram_request_multipart(
    token: str,
    method: str,
    *,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> dict | list:
    body, boundary = encode_multipart(fields=fields, files=files)
    request = urllib.request.Request(
        api_url(token, method),
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"Telegram HTTP error {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Telegram network error: {error.reason}") from error

    if not parsed.get("ok"):
        raise RuntimeError(parsed.get("description", f"Telegram API call failed: {method}"))
    return parsed["result"]


def send_message(token: str, chat_id: int, text: str) -> None:
    telegram_request_json(token, "sendMessage", {"chat_id": chat_id, "text": text})


def send_document(token: str, chat_id: int, filename: str, payload: bytes, caption: str) -> None:
    telegram_request_multipart(
        token,
        "sendDocument",
        fields={"chat_id": str(chat_id), "caption": caption},
        files={"document": (filename, payload, "audio/midi")},
    )


def get_file_bytes(token: str, file_id: str) -> bytes:
    result = telegram_request_json(token, "getFile", {"file_id": file_id})
    path = result.get("file_path")
    if not path:
        raise RuntimeError("Telegram did not return file_path.")
    request = urllib.request.Request(file_url(token, path), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"Telegram file download failed {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Telegram file download network error: {error.reason}") from error


def default_preferences() -> ChatPreferences:
    style = normalize_style(os.getenv("IMIXING_BOT_STYLE", "balanced"))
    try:
        output_format = int(os.getenv("IMIXING_BOT_FORMAT", "1"))
    except ValueError:
        output_format = 1
    if output_format not in (0, 1):
        output_format = 1
    return ChatPreferences(style=style, output_format=output_format)


def command_name(text: str) -> str:
    head = text.strip().split(maxsplit=1)[0]
    if "@" in head:
        head = head.split("@", 1)[0]
    return head.lower()


def command_arg(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def format_preferences(preferences: ChatPreferences) -> str:
    return f"style={preferences.style}, format={preferences.output_format}"


def help_text() -> str:
    styles = ", ".join(list_style_names())
    return (
        "Отправьте MIDI-файл документом, и я пришлю исправленную версию.\n\n"
        "Команды:\n"
        "/start - краткая инструкция\n"
        "/help - список команд\n"
        "/styles - список доступных стилей\n"
        "/style piano - сменить стиль обработки\n"
        "/format 1 - выбрать формат 0 или 1\n"
        "/status - показать текущие настройки\n\n"
        f"Доступные стили: {styles}"
    )


def handle_command(token: str, chat_id: int, text: str, preferences: ChatPreferences) -> None:
    name = command_name(text)
    argument = command_arg(text)

    if name in {"/start", "/help"}:
        send_message(token, chat_id, help_text())
        return

    if name == "/styles":
        send_message(token, chat_id, "Стили: " + ", ".join(list_style_names()))
        return

    if name == "/status":
        send_message(token, chat_id, "Текущие настройки: " + format_preferences(preferences))
        return

    if name == "/style":
        if not argument:
            send_message(token, chat_id, "Укажите стиль, например: /style piano")
            return
        try:
            preferences.style = normalize_style(argument)
        except ValueError as error:
            send_message(token, chat_id, str(error))
            return
        send_message(token, chat_id, "Стиль обновлён: " + preferences.style)
        return

    if name == "/format":
        if argument not in {"0", "1"}:
            send_message(token, chat_id, "Укажите /format 0 или /format 1")
            return
        preferences.output_format = int(argument)
        send_message(token, chat_id, "Формат обновлён: " + argument)
        return

    send_message(token, chat_id, "Неизвестная команда. Используйте /help.")


def handle_document(token: str, chat_id: int, document: dict, preferences: ChatPreferences) -> None:
    filename = document.get("file_name") or "upload.mid"
    if not filename.lower().endswith((".mid", ".midi")):
        send_message(token, chat_id, "Пришлите файл именно в формате .mid или .midi")
        return

    file_id = document.get("file_id")
    if not file_id:
        send_message(token, chat_id, "Не удалось получить file_id у документа.")
        return

    send_message(token, chat_id, f"Обрабатываю {filename} в стиле {preferences.style}...")
    try:
        payload = get_file_bytes(token, file_id)
        result = fix_midi_bytes(
            payload,
            source_name=filename,
            options=MidiFixOptions(
                style=preferences.style,
                output_format=preferences.output_format,
                include_track_titles=False,
            ),
        )
    except ValueError as error:
        send_message(token, chat_id, f"Ошибка MIDI: {error}")
        return
    except RuntimeError as error:
        send_message(token, chat_id, f"Ошибка Telegram API: {error}")
        return
    except Exception as error:  # noqa: BLE001
        send_message(token, chat_id, f"Неожиданная ошибка: {error}")
        return

    caption = (
        f"Готово. style={result.stats.style}, grid={result.stats.quantize_grid}, "
        f"notes {result.stats.original_note_count}->{result.stats.edited_note_count}"
    )
    send_document(token, chat_id, result.output_filename, result.midi_bytes, caption)


def process_update(
    token: str,
    update: dict,
    chat_states: dict[int, ChatPreferences],
    defaults: ChatPreferences,
) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    preferences = chat_states.setdefault(
        chat_id,
        ChatPreferences(style=defaults.style, output_format=defaults.output_format),
    )

    text = message.get("text")
    if isinstance(text, str) and text.startswith("/"):
        handle_command(token, chat_id, text, preferences)
        return

    document = message.get("document")
    if isinstance(document, dict):
        handle_document(token, chat_id, document, preferences)
        return

    if text:
        send_message(token, chat_id, "Пришлите MIDI-файл документом или используйте /help.")


def poll_updates(token: str) -> None:
    defaults = default_preferences()
    chat_states: dict[int, ChatPreferences] = {}
    offset: int | None = None

    while True:
        payload: dict[str, int] = {"timeout": 30}
        if offset is not None:
            payload["offset"] = offset
        try:
            updates = telegram_request_json(token, "getUpdates", payload)
            for update in updates:
                offset = update["update_id"] + 1
                process_update(token, update, chat_states, defaults)
        except KeyboardInterrupt:
            raise
        except Exception as error:  # noqa: BLE001
            print(f"Bot loop error: {error}")
            time.sleep(2)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN before starting the Telegram bot.")

    print("Starting iMixing MIDI Telegram bot...")
    print("Default preferences:", format_preferences(default_preferences()))
    poll_updates(token)
