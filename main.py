import requests
import os

# === Конфигурация ===
SRC_ACCOUNT_ID = os.environ["SRC_ACCOUNT_ID"]  # ID аккаунта-источника
DST_ACCOUNT_ID = os.environ["DST_ACCOUNT_ID"]  # ID аккаунта-приёмника
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]      # Твой API токен

# Читаем список имён шаблонов и убираем лишние пробелы
TEMPLATE_NAMES = [name.strip() for name in os.environ["TEMPLATE_NAMES"].split(",")]

API_URL = "https://graph.facebook.com/v20.0"


# Получить список шаблонов аккаунта
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


# Создать шаблон в другом аккаунте
def create_template(account_id, template):
    url = f"{API_URL}/{account_id}/message_templates"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    payload = {
        "name": template["name"],
        "category": template["category"],
        "language": template["language"],
        "components": template["components"]
    }

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"❌ Ошибка создания {template['name']}: {resp.text}")
    else:
        print(f"✅ Шаблон {template['name']} создан")


def main():
    print("Получаем шаблоны из источника...")
    src_templates = get_templates(SRC_ACCOUNT_ID)

    print("Получаем шаблоны из целевого аккаунта...")
    dst_templates = get_templates(DST_ACCOUNT_ID)
    dst_names = [tpl["name"] for tpl in dst_templates]

    # Фильтруем только полные совпадения и которых нет в целевом аккаунте
    selected = [
        tpl for tpl in src_templates
        if tpl["name"] in TEMPLATE_NAMES and tpl["name"] not in dst_names
    ]

    if not selected:
        print("⚠️ Нет шаблонов для копирования (или уже все есть в целевом аккаунте).")
        return

    print(f"Будет скопировано {len(selected)} шаблонов: {[t['name'] for t in selected]}")

    for tpl in selected:
        create_template(DST_ACCOUNT_ID, tpl)


if __name__ == "__main__":
    main()
