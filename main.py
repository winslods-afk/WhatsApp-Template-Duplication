import requests
import os

SRC_ACCOUNT_ID = os.environ["SRC_ACCOUNT_ID"]
DST_ACCOUNT_ID = os.environ["DST_ACCOUNT_ID"]
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
TEMPLATE_NAMES = [name.strip() for name in os.environ["TEMPLATE_NAMES"].split(",")]

API_URL = "https://graph.facebook.com/v20.0"

def get_templates(account_id):
    url = f"{API_URL}/{account_id}/message_templates"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    params = {"limit": 100}
    templates = []

    while True:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise Exception(f"Ошибка при получении шаблонов: {resp.text}")
        data = resp.json()
        templates.extend(data.get("data", []))
        if "paging" in data and "next" in data["paging"]:
            url = data["paging"]["next"]
            params = {}
        else:
            break
    return templates

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
    templates = get_templates(SRC_ACCOUNT_ID)

   selected = [tpl for tpl in templates if tpl["name"] in TEMPLATE_NAMES]

    if not selected:
        print("⚠️ Нет шаблонов с указанными именами.")
        return

    print(f"Будет скопировано {len(selected)} шаблонов: {[t['name'] for t in selected]}")

    for tpl in selected:
        create_template(DST_ACCOUNT_ID, tpl)

if __name__ == "__main__":
    main()

