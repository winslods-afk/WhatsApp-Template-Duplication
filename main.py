import requests
import os
from urllib.parse import urlparse
import mimetypes
import csv

SRC_ACCOUNT_ID = os.environ["SRC_ACCOUNT_ID"]
DST_ACCOUNT_ID = os.environ["DST_ACCOUNT_ID"]
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]

TEMPLATE_NAMES = [name.strip() for name in os.environ["TEMPLATE_NAMES"].split(",")]
API_URL = "https://graph.facebook.com/v20.0"
LOG_FILE = "templates_migration_log.csv"


def get_templates(account_id):
    url = f"{API_URL}/{account_id}/message_templates"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    params = {"limit": 100}
    templates = []

    while True:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise Exception(f"Ошибка при получении шаблонов ({account_id}): {resp.text}")
        data = resp.json()
        templates.extend(data.get("data", []))
        if "paging" in data and "next" in data["paging"]:
            url = data["paging"]["next"]
            params = {}
        else:
            break
    return templates


def upload_media(account_id, url):
    """Скачивает файл и загружает в целевой WABA, возвращает media_id"""
    print(f"⬇️ Скачиваем медиа: {url}")
    file_resp = requests.get(url)
    if file_resp.status_code != 200:
        raise Exception(f"Не удалось скачать медиа: {url}")

    filename = os.path.basename(urlparse(url).path)
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


def process_header(comp, account_id, template_name):
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
            new_comp["example"] = {"header_handle": [media_id]}
            return new_comp, media_id
        except Exception as e:
            print(f"⚠️ Не удалось обработать {header_format} для {template_name}: {e}")

    elif header_format == "LOCATION":
        if example:
            new_comp["example"] = example

    return new_comp, None


def process_buttons(comp):
    """Обрабатывает кнопки любого типа"""
    new_buttons = []
    for btn in comp.get("buttons", []):
        btn_type = btn.get("type")
        new_btn = {
            "type": btn_type,
            "text": btn.get("text")
        }
        if btn_type == "URL":
            new_btn["url"] = btn.get("url")
        elif btn_type == "PHONE_NUMBER":
            new_btn["phone_number"] = btn.get("phone_number")
        elif btn_type == "QUICK_REPLY":
            new_btn["payload"] = btn.get("payload")
        new_buttons.append(new_btn)
    return {"type": "BUTTONS", "buttons": new_buttons}


def create_template(account_id, template, csv_writer):
    url = f"{API_URL}/{account_id}/message_templates"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    payload = {
        "name": template["name"],
        "category": template["category"],
        "language": template["language"],
        "components": []
    }

    new_media_id = None

    for comp in template["components"]:
        if comp["type"] == "HEADER":
            new_comp, media_id = process_header(comp, account_id, template["name"])
            if media_id:
                new_media_id = media_id
        elif comp["type"] == "BODY":
            new_comp = {"type": "BODY", "text": comp["text"]}
        elif comp["type"] == "FOOTER":
            new_comp = {"type": "FOOTER", "text": comp["text"]}
        elif comp["type"] == "BUTTONS":
            new_comp = process_buttons(comp)
        else:
            new_comp = comp

        payload["components"].append(new_comp)

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"❌ Ошибка создания {template['name']}: {resp.text}")
        csv_writer.writerow([template["name"], template["language"], template["category"], "ERROR", new_media_id, resp.text])
    else:
        print(f"✅ Шаблон {template['name']} создан")
        csv_writer.writerow([template["name"], template["language"], template["category"], "OK", new_media_id, ""])


def main():
    print("Получаем шаблоны из источника...")
    src_templates = get_templates(SRC_ACCOUNT_ID)

    print("Получаем шаблоны из целевого аккаунта...")
    dst_templates = get_templates(DST_ACCOUNT_ID)
    dst_names = [tpl["name"] for tpl in dst_templates]

    selected = [
        tpl for tpl in src_templates
        if tpl["name"] in TEMPLATE_NAMES and tpl["name"] not in dst_names
    ]

    if not selected:
        print("⚠️ Нет шаблонов для копирования.")
        return

    print(f"Будет скопировано {len(selected)} шаблонов: {[t['name'] for t in selected]}")

    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Template Name", "Language", "Category", "Status", "New Media ID", "Error Message"])

        for tpl in selected:
            create_template(DST_ACCOUNT_ID, tpl, writer)


if __name__ == "__main__":
    main()
