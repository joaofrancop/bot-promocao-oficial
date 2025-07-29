import os
import json
import asyncio
import time
import requests # Importa requests para chamadas de API OAuth
from playwright.async_api import async_playwright, Page, BrowserContext, expect

# Função para carregar os cookies do JSON (não mais usada para login principal, mas mantida)
def load_cookies_from_json(json_string: str) -> list:
    # ... (manter o código da função load_cookies_from_json exatamente como na última versão robusta) ...
    # Eu vou omitir para não repetir, mas use a versão completa que te enviei antes.
    # Esta função não será o método principal de login agora, mas é bom mantê-la.
    pass # Substitua esta linha pelo código completo da função load_cookies_from_json


# Função para obter/atualizar o Access Token usando o Refresh Token
async def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    """
    Obtém um novo access_token e refresh_token usando o refresh_token existente.
    """
    print("DEBUG: Tentando renovar o Access Token com Refresh Token...")
    token_url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        response = requests.post(token_url, data=payload, headers=headers)
        response.raise_for_status()
        new_tokens = response.json()
        print("DEBUG: Access Token renovado com sucesso.")
        return new_tokens
    except requests.exceptions.HTTPError as e:
        print(f"ERRO: Falha ao renovar Access Token HTTP: {e}")
        print(f"Resposta do servidor: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ERRO: Falha ao renovar Access Token Request: {e}")
        return None

# Função para gerar links de afiliado usando a API do Mercado Livre (OAuth)
async def generate_affiliate_link_via_api(access_token: str, original_url: str, affiliate_tag: str) -> dict:
    """
    Gera um link de afiliado do Mercado Livre usando a API oficial.
    """
    # ATENÇÃO: Você precisará confirmar o endpoint exato para gerar links de afiliado via API.
    # O endpoint abaixo é um palpite baseado no que vimos no scraping.
    # Se este endpoint não funcionar, a API de afiliados pode não ter um endpoint público para isso.
    affiliate_api_url = "https://api.mercadolibre.com/affiliate-program/api/v2/affiliates/createLink"
    # OU pode ser algo como: "https://api.mercadolibre.com/users/me/affiliate_links" (exemplo)

    payload = {"urls": [original_url], "tag": affiliate_tag}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(affiliate_api_url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"ERRO API Afiliado HTTP: {e}")
        print(f"Resposta do servidor: {e.response.text}")
        return {"error": str(e), "response_content": e.response.text}
    except requests.exceptions.RequestException as e:
        print(f"ERRO API Afiliado Request: {e}")
        return {"error": str(e)}

# A função perform_ml_login não será mais o método principal de login
async def perform_ml_login(page: Page, username: str, password: str) -> bool:
    # ... (manter o código da função perform_ml_login exatamente como na última versão) ...
    pass # Substitua esta linha pelo código completo da função perform_ml_login

# A função generate_affiliate_links_with_playwright será refatorada para usar OAuth
async def generate_affiliate_links_with_playwright(product_urls: list, affiliate_tag: str) -> tuple[list, list]:
    """
    Gera links de afiliado do Mercado Livre usando a API OAuth 2.0.
    """
    print("Iniciando geração de links de afiliado com API OAuth 2.0...")
    
    # Obter credenciais OAuth dos secrets
    ml_client_id = os.getenv("ML_CLIENT_ID")
    ml_client_secret = os.getenv("ML_CLIENT_SECRET")
    ml_refresh_token = os.getenv("ML_REFRESH_TOKEN")

    if not all([ml_client_id, ml_client_secret, ml_refresh_token, affiliate_tag]):
        print("ERRO FATAL: Credenciais OAuth ou TAG de afiliado incompletas. Verifique os GitHub Secrets.")
        return [None] * len(product_urls), [None] * len(product_urls)
    
    current_access_token = None
    
    # 1. Obter/Renovar Access Token usando Refresh Token
    new_tokens = await refresh_access_token(ml_client_id, ml_client_secret, ml_refresh_token)
    if new_tokens and new_tokens.get("access_token"):
        current_access_token = new_tokens["access_token"]
        # ATENÇÃO: O refresh_token é de uso único. O novo refresh_token deve ser salvo!
        # Para um bot em GitHub Actions, isso significa atualizar o secret ML_REFRESH_TOKEN.
        # Isso é complexo e geralmente requer uma API externa ou intervenção manual.
        # Por enquanto, vamos usar o novo refresh_token para a próxima execução.
        # Em um sistema de produção, você precisaria de um serviço que atualize o secret.
        # Ou, para simplificar, você pode gerar um novo refresh_token manualmente quando o antigo expirar.
        print(f"DEBUG: NOVO REFRESH TOKEN OBTIDO: {new_tokens.get('refresh_token')}")
        print("AVISO: Você precisará atualizar o secret ML_REFRESH_TOKEN no GitHub com este novo valor manualmente após esta execução, ou implementar uma forma de fazê-lo automaticamente.")
        # Para este projeto, vamos assumir que você atualizará o secret manualmente quando este aviso aparecer.
    else:
        print("ERRO FATAL: Não foi possível obter ou renovar o Access Token. Verifique as credenciais OAuth.")
        return [None] * len(product_urls), [None] * len(product_urls)

    shorts = []
    longs = []
    quantidade_total = 0

    # 2. Gerar links para cada URL de produto usando o Access Token
    for original_url in product_urls:
        try:
            api_response = await generate_affiliate_link_via_api(current_access_token, original_url, affiliate_tag)
            
            if api_response and api_response.get("urls"):
                item = api_response["urls"][0]
                short_url = item.get("short_url")
                long_url = item.get("long_url")

                if not short_url or not long_url:
                    shorts.append(None)
                    longs.append(None)
                    print(f"AVISO: API não retornou short/long URL para {original_url}. Resposta: {api_response}")
                else:
                    shorts.append(short_url)
                    longs.append(long_url)
                    quantidade_total += 1
                    print(f"Link gerado ({quantidade_total} de {len(product_urls)}) para {original_url}: {short_url}")
            else:
                shorts.append(None)
                longs.append(None)
                print(f"ERRO: Resposta inesperada da API para {original_url}: {api_response}")

        except Exception as e:
            print(f"ERRO ao gerar link de afiliado para {original_url} via API: {e}")
            shorts.append(None)
            longs.append(None)
        
        await asyncio.sleep(0.6) # Manter um pequeno delay entre as chamadas de API

    print("Geração de links de afiliado via API OAuth concluída.")
    return shorts, longs

