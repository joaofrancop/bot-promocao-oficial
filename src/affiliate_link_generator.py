import os
import json
import asyncio
import time # Importe time para usar time.sleep
from playwright.async_api import async_playwright, Page, BrowserContext, expect

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
               cookie['sameSite'] is None: 
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
                # Um timestamp em milissegundos é geralmente > 10^12 (após 2001)
                # Um timestamp em segundos é geralmente < 10^11 (até 2001)
                # Usar um valor limite como 2524608000 (após 2050) é um bom heuristic.
                if cookie['expirationDate'] > 2524608000: 
                    cookie['expires'] = int(cookie['expirationDate'] / 1000)
                else: 
                    cookie['expires'] = int(cookie['expirationDate'])
            else:
                # Se 'expirationDate' não for numérico, define um expires padrão (ex: 7 dias a partir de agora)
                print(f"Aviso: 'expirationDate' do cookie '{cookie.get('name')}' não é numérico. Definindo padrão.")
                cookie['expires'] = int(time.time() + 3600 * 24 * 7)
            del cookie['expirationDate'] # Remove a chave original para evitar duplicidade ou conflito
        elif 'expires' not in cookie: # Se nem 'expirationDate' nem 'expires' existem
            # Adiciona um expires padrão (ex: 7 dias)
            cookie['expires'] = int(time.time() + 3600 * 24 * 7)
        # Garante que 'expires' é um inteiro
        if 'expires' in cookie and not isinstance(cookie['expires'], int):
            cookie['expires'] = int(cookie['expires'])

        # --- REMOÇÃO DE ATRIBUTOS NÃO SUPORTADOS PELO PLAYWRIGHT ---
        # Removê-los para evitar avisos ou erros
        cookie.pop('hostOnly', None)
        cookie.pop('session', None)
        cookie.pop('storeId', None) 
        cookie.pop('id', None) # 'id' também pode ser problemático, remover

        processed_cookies.append(cookie)

    print("DEBUG: Finalizado load_cookies_from_json. Total de cookies processados:", len(processed_cookies))
    return processed_cookies

# A função perform_ml_login permanece a mesma, pois a estratégia principal é cookies
async def perform_ml_login(page: Page, username: str, password: str) -> bool:
    """
    Tenta realizar o login no Mercado Livre com usuário e senha.
    Retorna True se o login for bem-sucedido, False caso contrário.
    """
    print("DEBUG: Tentando realizar login no Mercado Livre com usuário e senha...")
    try:
        await page.goto("https://www.mercadolivre.com.br/login", wait_until="load", timeout=30000)

        # Inspecione o HTML da página de login do Mercado Livre para encontrar os seletores corretos
        # Estes são exemplos e PRECISAM ser ajustados aos seletores reais do ML
        email_input_selector = 'input[name="user_id"]' 
        continue_button_selector = 'button[type="submit"]' 
        password_input_selector = 'input[name="password"]' 
        login_button_selector = 'button[type="submit"]' 

        await page.wait_for_selector(email_input_selector, timeout=10000)
        await page.fill(email_input_selector, username)
        await page.click(continue_button_selector)

        await page.wait_for_selector(password_input_selector, timeout=10000)
        await page.fill(password_input_selector, password)
        await page.click(login_button_selector)

        await page.wait_for_url(lambda url: "mercadolivre.com.br" in url and "login" not in url and "security" not in url, timeout=30000)
        
        if "login" in page.url or "security" in page.url or "verifica" in page.url or "seguridad" in page.url:
            print(f"DEBUG: AVISO: Login direto falhou ou 2FA ativado. Redirecionado para: {page.url}")
            return False

        print("DEBUG: Login direto no Mercado Livre bem-sucedido.")
        return True

    except Exception as e:
        print(f"DEBUG: ERRO durante o login direto no Mercado Livre: {e}")
        return False

# A função generate_affiliate_links_with_playwright foi atualizada para usar a lógica de login
async def generate_affiliate_links_with_playwright(product_urls: list, affiliate_tag: str):
    """
    Gera links de afiliado do Mercado Livre usando Playwright, tentando login direto ou cookies.
    Espera que os secrets ML_USERNAME, ML_PASSWORD, ML_COOKIES_JSON e ML_AFFILIATE_TAG estejam configurados.
    """
    print("Iniciando geração de links de afiliado com Playwright...")
    
    # Obter credenciais e secrets
    ml_username = os.getenv("ML_USERNAME")
    ml_password = os.getenv("ML_PASSWORD")
    cookies_json = os.getenv("ML_COOKIES_JSON")

    if not affiliate_tag:
        print("ERRO: A TAG de afiliado não foi definida. Os links podem não ser gerados corretamente.")
    
    shorts = []
    longs = []
    quantidade_total = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context()
        page = await context.new_page()

        logged_in = False

        # Tentar login com cookies primeiro (se ML_COOKIES_JSON estiver presente)
        if cookies_json:
            print("DEBUG: Tentando login com cookies...")
            try:
                cookies = load_cookies_from_json(cookies_json)
                await context.add_cookies(cookies) 
                # Navegar para um URL simples para verificar se os cookies foram carregados
                await page.goto("https://www.mercadolivre.com.br/", wait_until="load", timeout=30000)
                print(f"DEBUG: URL após carregar cookies e ir para home: {page.url}")

                await page.goto("https://www.mercadolivre.com.br/affiliate-program/panel", wait_until="load", timeout=30000)
                print(f"DEBUG: URL após tentar ir para painel de afiliados: {page.url}")

                if "login" not in page.url and "security" not in page.url and "verifica" not in page.url and "seguridad" not in page.url:
                    print("DEBUG: Sessão ativa com cookies.")
                    logged_in = True
                else:
                    print(f"DEBUG: Cookies inválidos ou expirados. Redirecionado para: {page.url}")
            except Exception as e:
                print(f"DEBUG: Erro ao carregar cookies ou navegar com eles: {e}")
        
        # Se o login com cookies falhou ou não foi tentado, tenta login direto
        if not logged_in and ml_username and ml_password:
            print("DEBUG: Tentando login direto com usuário e senha...")
            logged_in = await perform_ml_login(page, ml_username, ml_password)
        
        if not logged_in:
            print("ERRO FATAL: Não foi possível fazer login no Mercado Livre com cookies ou credenciais diretas.")
            print("Por favor, verifique ML_COOKIES_JSON, ML_USERNAME/ML_PASSWORD e desative 2FA se possível.")
            await browser.close()
            return [None] * len(product_urls), [None] * len(product_urls)

        print("Sessão ativa no Mercado Livre para gerar links.")
        
        # Lógica para gerar links (esta parte permanece a mesma)
        input_url_selector = 'input[name="url"]' 
        generate_button_selector = 'button[type="submit"]' 

        try:
            await page.goto("https://www.mercadolivre.com.br/affiliate-program/panel", wait_until="load", timeout=30000)
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
