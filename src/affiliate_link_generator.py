import os
import json
import asyncio
import time
from playwright.async_api import async_playwright, Page, BrowserContext

# Função para carregar os cookies do JSON (VERSÃO MAIS ROBUSTA E FINAL)
def load_cookies_from_json(json_string: str) -> list:
    """Converte uma string JSON de cookies em um formato que o Playwright entenda,
    tratando atributos como sameSite, url/domain e expires para garantir compatibilidade.
    """
    cookies = json.loads(json_string)
    
    valid_same_site_values = ["Strict", "Lax", "None"] 
    default_base_url = "https://www.mercadolivre.com.br/" 

    processed_cookies = [] 
    for cookie in cookies:
        # Garante que o cookie seja um dicionário e contenha as chaves básicas
        if not isinstance(cookie, dict) or 'name' not in cookie or 'value' not in cookie:
            print(f"Aviso: Cookie malformado (faltando nome/valor) ignorado: {cookie}")
            continue 

        # --- TRATAMENTO PARA 'url' ou 'domain' ---
        # Playwright exige 'url'. Se não houver, tenta construir a partir de 'domain' e 'path'.
        # Se nem 'domain' for útil, usa uma URL padrão.
        if 'url' not in cookie or not cookie['url']: # Se 'url' não existe ou está vazia
            if 'domain' in cookie and cookie['domain']: # Se 'domain' existe e não está vazio
                domain = cookie['domain']
                # Remover o ponto inicial e 'www.' se houver
                if domain.startswith('.'):
                    domain = domain[1:]
                if domain.startswith('www.'): # Adicionado para lidar com .www.
                    domain = domain[4:]
                
                path = cookie.get('path', '/') 
                cookie['url'] = f"https://{domain}{path}"
            else:
                # Fallback se não há 'url' nem 'domain' útil
                cookie['url'] = default_base_url
        # --- FIM TRATAMENTO 'url' ou 'domain' ---

        # --- TRATAMENTO PARA sameSite ---
        if 'sameSite' in cookie:
            # Converte 'null' (de JSON) ou string vazia para a string "None"
            if cookie['sameSite'] not in valid_same_site_values or \
               cookie['sameSite'] == "" or \
               cookie['sameSite'] is None: # Lida com o 'null' do JSON
                cookie['sameSite'] = "None" 
        else:
            # Se 'sameSite' não está presente, adicione-o como "None" explicitamente
            cookie['sameSite'] = "None"
        # --- FIM TRATAMENTO sameSite ---

        # --- TRATAMENTO PARA 'expires' ---
        # Playwright espera um timestamp UNIX em segundos (inteiro)
        if 'expirationDate' in cookie: # O JSON do Cookie-Editor usa 'expirationDate'
            if isinstance(cookie['expirationDate'], (int, float)):
                # Se for um timestamp em milissegundos (muito grande), converte para segundos
                if cookie['expirationDate'] > 2524608000: # Exemplo: timestamp após 2050
                    cookie['expires'] = int(cookie['expirationDate'] / 1000)
                else: # Já está em segundos ou é um valor pequeno (pode ser 0 para sessão)
                    cookie['expires'] = int(cookie['expirationDate'])
            else:
                # Se não for numérico, define um expires padrão (ex: 7 dias a partir de agora)
                print(f"Aviso: 'expirationDate' do cookie '{cookie.get('name')}' não é numérico. Definindo padrão.")
                cookie['expires'] = int(time.time() + 3600 * 24 * 7)
            del cookie['expirationDate'] # Remove a chave original para evitar duplicidade ou conflito
        elif 'expires' not in cookie: # Se nem 'expirationDate' nem 'expires' existem
            # Adiciona um expires padrão (ex: 7 dias)
            cookie['expires'] = int(time.time() + 3600 * 24 * 7)
        # Garante que 'expires' é um inteiro
        if 'expires' in cookie and not isinstance(cookie['expires'], int):
            cookie['expires'] = int(cookie['expires'])

        # --- TRATAMENTO PARA 'hostOnly' e 'session' ---
        # Playwright não usa 'hostOnly' e 'session' diretamente, mas pode vir do JSON
        # Removê-los para evitar avisos ou erros, se não forem necessários para o Playwright
        cookie.pop('hostOnly', None)
        cookie.pop('session', None)
        cookie.pop('storeId', None) # Outro campo não usado pelo Playwright

        processed_cookies.append(cookie)

    return processed_cookies

async def generate_affiliate_links_with_playwright(product_urls: list, affiliate_tag: str):
    """
    Gera links de afiliado do Mercado Livre usando Playwright e cookies de sessão.
    Espera que o secret ML_COOKIES_JSON e ML_AFFILIATE_TAG estejam configurados.
    """
    print("Iniciando geração de links de afiliado com Playwright via cookies...")
    
    cookies_json = os.getenv("ML_COOKIES_JSON")

    if not cookies_json:
        print("ERRO: O secret ML_COOKIES_JSON não foi definido ou está vazio. Login via cookies falhará.")
        return [None] * len(product_urls), [None] * len(product_urls) 

    if not affiliate_tag:
        print("ERRO: A TAG de afiliado não foi definida. Os links podem não ser gerados corretamente.")
    
    try:
        cookies = load_cookies_from_json(cookies_json)
    except json.JSONDecodeError as e:
        print(f"ERRO: Não foi possível decodificar o JSON dos cookies. Verifique o formato no secret. Erro: {e}")
        return [None] * len(product_urls), [None] * len(product_urls)

    shorts = []
    longs = []
    quantidade_total = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context()
        
        await context.add_cookies(cookies) 
        page = await context.new_page()

        print("Tentando acessar o painel de afiliados com cookies...")
        try:
            await page.goto("https://www.mercadolivre.com.br/affiliate-program/panel", wait_until="load", timeout=30000)
            if "login" in page.url or "security" in page.url or "verifica" in page.url or "seguridad" in page.url:
                print(f"ERRO: Os cookies expiraram, são inválidos ou 2FA ativado. Redirecionado para a página: {page.url}")
                print("Por favor, faça login manual no Mercado Livre, exporte os novos cookies e atualize o secret ML_COOKIES_JSON.")
                await browser.close()
                return [None] * len(product_urls), [None] * len(product_urls)

            print("Sessão aparentemente ativa no painel de afiliados.")

        except Exception as e:
            print(f"ERRO na navegação inicial para o painel de afiliados: {e}. Cookies podem estar inválidos.")
            await browser.close()
            return [None] * len(product_urls), [None] * len(product_urls)


        input_url_selector = 'input[name="url"]' 
        generate_button_selector = 'button[type="submit"]' 

        try:
            await page.wait_for_selector(input_url_selector, timeout=10000) 
            await page.wait_for_selector(generate_button_selector, timeout=10000) 
        except Exception as e:
            print(f"ERRO: Não foi possível encontrar os seletores do formulário de geração de links. O layout do painel pode ter mudado. Erro: {e}")
            await browser.close()
            return [None] * len(product_urls), [None] * len(product_urls)


        for original_url in product_urls:
            try:
                await page.goto("https://www.mercadolivre.com.br/affiliate-program/panel", wait_until="load", timeout=30000)
                await page.wait_for_selector(input_url_selector, timeout=10000) 
                
                await page.fill(input_url_selector, original_url)
                
                async with page.expect_response(
                    lambda response: "affiliates/createLink" in response.url and response.status == 200
                ) as response_info:
                    await page.click(generate_button_selector)
                
                response_data = await response_info.value.json()
                item = response_data.get("urls", [{}])[0]
                short_url = item.get("short_url")
                long_url = item.get("long_url")

                if not short_url or not long_url:
                    shorts.append(None)
                    longs.append(None)
                    print(f"Não foi possível gerar link para: {original_url}. Resposta API: {response_data}")
                else:
                    shorts.append(short_url)
                    longs.append(long_url)
                    quantidade_total += 1
                    print(f"Link gerado ({quantidade_total} de {len(product_urls)}) para {original_url}: {short_url}")

            except Exception as e:
                print(f"Erro ao gerar link de afiliado para {original_url}: {e}")
                shorts.append(None)
                longs.append(None)
            
            await asyncio.sleep(0.6)

        await browser.close()
        return shorts, longs
