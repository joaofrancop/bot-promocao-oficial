import requests
import json

def send_telegram_message(bot_token: str, chat_id: str, message: str, image_url: str = None) -> dict:
    """
    Envia uma mensagem para um chat/grupo do Telegram.
    Pode incluir uma imagem com a mensagem como caption.
    """
    if image_url:
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": message,
            "parse_mode": "Markdown" # Permite negrito, itálico, etc.
        }
    else:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Levanta um erro para status HTTP ruins
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"ERRO Telegram HTTP: {e}")
        print(f"Conteúdo da resposta: {e.response.text}")
        return {"error": str(e), "response_content": e.response.text}
    except requests.exceptions.RequestException as e:
        print(f"ERRO Telegram Request: {e}")
        return {"error": str(e)}

