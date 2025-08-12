import requests
import mimetypes
import os
import csv
from urllib.parse import urlparse

# Настройки
ACCESS_TOKEN = "ВАШ_ACCESS_TOKEN"
API_URL = "https://graph.facebook.com/v20.0"
SOURCE_WABA = "SOURCE_WHATSAPP_BUSINESS_ACCOUNT_ID"
TARGET_WABA = "TARGET_WHATSAPP_BUSINESS_ACCOUNT_ID"
TEMPLATE_NAME_TO_COPY = "test_roman1"  # Полное совпадение имени

# Путь для CSV лога
LOG_FILE = "template_copy_log.csv"


def log_result(template_name, status, components_info, media_ids, buttons_info):
    """Сохраняет информацию о копировании в CSV"""
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Template Name", "Status", "Components", "Media IDs", "Buttons"])
        writer.writerow([
            template_name,
            status,
            ", ".join(components_info),
            ", ".join(media_ids),
            ", ".join(buttons_info)
        ])


def upload_media(account_id, media_url):
    """Скачивает и загружает медиа в целевой WABA, возвращает media_id"""
    print(f"⬇️ Скачиваем медиа: {media_url}")
    file_resp = requests.get(media_url, stream=True)
    if file_resp.status_code != 200:
        raise Exception(f"Не удалось скачать медиа: {media_url}")

    filename = os.path.basename(urlparse(media_url).path)
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"

    upload_url = f"{API_URL}/{account_id}/media"
    files = {
        "file": (filename, file_resp.content, mime_type)
    }
    data = {
        "messaging_product": "whatsapp"
    }
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    print(f"📤 Загружаем медиа в целевой WABA...")
    resp = requests.post(upload_url, headers=headers, files=files, data=data)
    if resp.status_code != 200:
        raise Exception(f"Ошибка загрузки медиа: {resp.text}")

    media_id = resp.json().get("id")
    print(f"✅ Медиа загружено, media_id={media_id}")
    return media_id


def process_header(comp, account_id, template_name, media_ids):
    """Обрабатывает HEADER в зависимости от формата"""
    new_comp = {"type": comp["type"], "format": comp.get("format")}
    header_format = comp.get("format")
    example = comp.get("example")

    if header_format == "TEXT":
        new_comp["text"] = comp.get("text", "")
        if example:
            new_comp["example"] = example

    elif header_format in ["IMAGE", "VIDEO", "DOCUMENT"]:
        try:
            media_url = example["header_handle"][0]
            media_id = upload_media(account_id, media_url)
            media_ids.append(media_id)
            new_comp["example"] = {"header_handle": [media_id]}
        except Exception as e:
            print(f"⚠️ Не удалось обработать {header_format} для {template_name}: {e}")

    elif header_format == "LOCATION":
        if example:
            new_comp["example"] = example

    return new_comp


def process_buttons(buttons, buttons_info):
    """Приводит кнопки к формату API v20"""
    new_buttons = []
    for btn in buttons:
        btn_type = btn.get("type")
        text = btn.get("text", "")
        buttons_info.append(f"{btn_type}:{text}")

        if btn_type == "QUICK_REPLY":
            new_buttons.append({"type": "QUICK_REPLY", "text": text})

        elif btn_type == "URL":
            new_buttons.append({
                "type": "URL",
                "text": text,
                "url": btn.get("url", "")
            })

        elif btn_type == "PHONE_NUMBER":
            new_buttons.append({
                "type": "PHONE_NUMBER",
                "text": text,
                "phone_number": btn.get("phone_number", "")
            })

        else:
            print(f"⚠️ Неизвестный тип кнопки: {btn_type}")

    return new_buttons


def get_templates(account_id):
    """Получает список шаблонов"""
    url = f"{API_URL}/{account_id}/message_templates"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Ошибка получения шаблонов: {resp.text}")
    return resp.json().get("data", [])


def create_template(account_id, template):
    """Создаёт шаблон в целевом аккаунте"""
    url = f"{API_URL}/{account_id}/message_templates"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, headers=headers, json=template)
    return resp


# ==== Основной код ====
print("Получаем шаблоны из источника...")
source_templates = get_templates(SOURCE_WABA)

# Ищем точное совпадение по имени
template_to_copy = next((t for t in source_templates if t["name"] == TEMPLATE_NAME_TO_COPY), None)
if not template_to_copy:
    print(f"❌ Шаблон {TEMPLATE_NAME_TO_COPY} не найден в источнике")
else:
    print(f"Найден шаблон: {template_to_copy['name']}")

    components_info = []
    media_ids = []
    buttons_info = []

    new_components = []
    for comp in template_to_copy.get("components", []):
        components_info.append(comp["type"])
        if comp["type"] == "HEADER":
            new_components.append(process_header(comp, TARGET_WABA, template_to_copy["name"], media_ids))
        elif comp["type"] == "BUTTONS":
            new_components.append({
                "type": "BUTTONS",
                "buttons": process_buttons(comp.get("buttons", []), buttons_info)
            })
        else:
            new_components.append(comp)

    new_template = {
        "name": template_to_copy["name"],
        "category": template_to_copy.get("category", "UTILITY"),
        "components": new_components,
        "language": template_to_copy.get("language", "en")
    }

    resp = create_template(TARGET_WABA, new_template)
    if resp.status_code == 200:
        print(f"✅ Шаблон {template_to_copy['name']} создан")
        log_result(template_to_copy["name"], "SUCCESS", components_info, media_ids, buttons_info)
    else:
        print(f"❌ Ошибка создания {template_to_copy['name']}: {resp.text}")
        log_result(template_to_copy["name"], "FAIL", components_info, media_ids, buttons_info)
