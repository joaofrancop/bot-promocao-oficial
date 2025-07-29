import os
import json
import asyncio
import time
from playwright.async_api import async_playwright, Page, BrowserContext, expect

# Função para carregar os cookies do JSON (VERSÃO COM LOGS DE DEBUG APROFUNDADOS)
def load_cookies_from_json(json_string: str) -> list:
    """Converte uma string JSON de cookies em um formato que o Playwright entenda,
    tratando atributos como sameSite, url/domain e expires para garantir compatibilidade.
    Adiciona logs detalhados para depuração de cookies.
    """
    print("DEBUG: Iniciando load_cookies_from_json...")
    cookies = json.loads(json_string)
    
    valid_same_site_values = ["Strict", "Lax", "None"] 
    default_base_url = "https://www.mercadolivre.com.br/" 

    processed_cookies = [] 
    for i, cookie in enumerate(cookies):
        print(f"\nDEBUG: --- Processando cookie {i+1}/{len(cookies)}: '{cookie.get('name', 'N/A')}' ---")
        print(f"DEBUG: Cookie Original: {cookie}")

        if not isinstance(cookie, dict) or 'name' not in cookie or 'value' not in cookie:
            print(f"DEBUG: AVISO: Cookie malformado (faltando nome/valor) ignorado: {cookie}")
            continue 

        temp_cookie = cookie.copy() 

        try:
            # --- TRATAMENTO PARA 'url' ou 'domain' ---
            original_url_attr = temp_cookie.get('url', None)
            original_domain_attr = temp_cookie.get('domain', None)
            original_path_attr = temp_cookie.get('path', None)

            if 'url' in temp_cookie and temp_cookie['url']:
                pass 
            elif 'domain' in temp_cookie and temp_cookie['domain']:
                domain = temp_cookie['domain']
                if domain.startswith('.'):
                    domain = domain[1:]
                if domain.startswith('www.'): 
                    domain = domain[4:]
                
                path = temp_cookie.get('path', '/') 
                temp_cookie['url'] = f"https://{domain}{path}"
                print(f"DEBUG: Cookie '{temp_cookie['name']}' URL inferida: {temp_cookie['url']} (Original Domain: '{original_domain_attr}', Original Path: '{original_path_attr}')")
            else:
                temp_cookie['url'] = default_base_url
                print(f"DEBUG: Cookie '{temp_cookie['name']}' sem URL/Domínio válido. Usando fallback URL: {temp_cookie['url']}")
            # --- FIM TRATAMENTO 'url' ou 'domain' ---

            # --- TRATAMENTO PARA sameSite ---
            original_same_site_attr = temp_cookie.get('sameSite', None)
            if 'sameSite' in temp_cookie:
                if temp_cookie['sameSite'] not in valid_same_site_values or \
                   temp_cookie['sameSite'] == "" or \
                   temp_cookie['sameSite'] is None: 
                    temp_cookie['sameSite'] = "None" 
                    print(f"DEBUG: Cookie '{temp_cookie['name']}' sameSite inválido/vazio. Definido como 'None'. (Original: '{original_same_site_attr}')")
            else:
                temp_cookie['sameSite'] = "None"
                print(f"DEBUG: Cookie '{temp_cookie['name']}' sem sameSite. Definido como 'None'.")
            # --- FIM TRATAMENTO sameSite ---

            # --- TRATAMENTO PARA 'expires' ---
            original_expires_attr = temp_cookie.get('expires', temp_cookie.get('expirationDate', None))
            if 'expirationDate' in temp_cookie: 
                if isinstance(temp_cookie['expirationDate'], (int, float)):
                    if temp_cookie['expirationDate'] > 2524608000: 
                        temp_cookie['expires'] = int(temp_cookie['expirationDate'] / 1000)
                    else: 
                        temp_cookie['expires'] = int(temp_cookie['expirationDate'])
                else:
                    print(f"DEBUG: AVISO: 'expirationDate' do cookie '{temp_cookie['name']}' não é numérico. Definindo padrão.")
                    temp_cookie['expires'] = int(time.time() + 3600 * 24 * 7) 
                del temp_cookie['expirationDate'] 
            elif 'expires' not in temp_cookie: 
                temp_cookie['expires'] = int(time.time() + 3600 * 24 * 7)
            
            if 'expires' in temp_cookie and not isinstance(temp_cookie['expires'], int):
                temp_cookie['expires'] = int(temp_cookie['expires'])
                print(f"DEBUG: Cookie '{temp_cookie['name']}' expires convertido para int: {temp_cookie['expires']} (Original: '{original_expires_attr}')")
            # --- FIM TRATAMENTO 'expires' ---

            # --- REMOÇÃO DE ATRIBUTOS NÃO SUPORTADOS PELO PLAYWRIGHT ---
            removed_attrs = []
            for attr in ['hostOnly', 'session', 'storeId', 'id']: 
                if attr in temp_cookie:
                    temp_cookie.pop(attr)
                    removed_attrs.append(attr)
            if removed_attrs:
                print(f"DEBUG: Cookie '{temp_cookie['name']}' atributos removidos: {', '.join(removed_attrs)}")
            # --- FIM REMOÇÃO ---

            processed_cookies.append(temp_cookie)
            print(f"DEBUG: Cookie '{temp_cookie['name']}' Processado Final: {temp_cookie}")

        except Exception as e:
            print(f"DEBUG: ERRO INESPERADO ao processar cookie '{cookie.get('name', 'N/A')}': {e}")
            print(f"DEBUG: Cookie que causou o erro: {cookie}")
            continue 

    print("DEBUG: Finalizado load_cookies_from_json. Total de cookies processados:", len(processed_cookies))
    return processed_cookies

# A função perform_ml_login permanece a mesma
async def perform_ml_login(page: Page, username: str, password: str) -> bool:
    """
    Tenta realizar o login no Mercado Livre com usuário e senha.
    Retorna True se o login for bem-sucedido, False caso contrário.
    """
    print("DEBUG: Tentando realizar login no Mercado Livre com usuário e senha...")
    try:
        await page.goto("https://www.mercadolivre.com.br/login", wait_until="load", timeout=30000)

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

# A função generate_affiliate_links_with_playwright foi atualizada para tentar adicionar cookies um a um
async def generate_affiliate_links_with_playwright(product_urls: list, affiliate_tag: str):
    """
    Gera links de afiliado do Mercado Livre usando Playwright, tentando login direto ou cookies.
    Espera que os secrets ML_USERNAME, ML_PASSWORD, ML_COOKIES_JSON e ML_AFFILIATE_TAG estejam configurados.
    """
    print("Iniciando geração de links de afiliado com Playwright...")
    
    ml_username = os.getenv("ML_USERNAME")
    ml_password = os.getenv("ML_PASSWORD")
    ml_session_state_json = os.getenv("ML_SESSION_STATE") # NOVO SECRET
    cookies_json = os.getenv("ML_COOKIES_JSON") # Mantido para fallback de cookies diretos

    if not affiliate_tag:
        print("ERRO: A TAG de afiliado não foi definida. Os links podem não ser gerados corretamente.")
    
    shorts = []
    longs = []
    quantidade_total = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) 
        context = None # Inicializa context como None
        page = None # Inicializa page como None

        logged_in = False

        # --- Tentar carregar estado da sessão (ML_SESSION_STATE) ---
        if ml_session_state_json:
            print("DEBUG: Tentando carregar estado da sessão do Playwright (ML_SESSION_STATE)...")
            try:
                session_state = json.loads(ml_session_state_json)
                context = await browser.new_context(storage_state=session_state)
                page = await context.new_page()
                
                await page.goto("https://www.mercadolivre.com.br/affiliate-program/panel", wait_until="load", timeout=30000)
                if "login" not in page.url and "security" not in page.url and "verifica" not in page.url and "seguridad" not in page.url:
                    print("DEBUG: Sessão ativa carregada do estado salvo (ML_SESSION_STATE).")
                    logged_in = True
                else:
                    print(f"DEBUG: Estado da sessão inválido ou expirado (ML_SESSION_STATE). Redirecionado para: {page.url}")
                    # Se o estado falhou, fechar o contexto e tentar outra abordagem
                    await context.close() 
                    context = None # Resetar contexto
            except Exception as e:
                print(f"DEBUG: ERRO ao carregar ou usar estado da sessão (ML_SESSION_STATE): {e}")
                context = None # Resetar contexto
        
        # --- Tentar login com cookies (ML_COOKIES_JSON) se o estado da sessão falhou ---
        if not logged_in and cookies_json:
            print("DEBUG: Estado da sessão falhou ou não fornecido. Tentando login com cookies (ML_COOKIES_JSON)...")
            if not context: # Se o contexto não foi criado antes (porque ML_SESSION_STATE falhou)
                context = await browser.new_context() 
                page = await context.new_page() # Nova página para o novo contexto
            try:
                processed_cookies_for_playwright = load_cookies_from_json(cookies_json) 

                successful_cookies_count = 0
                for i, cookie_obj in enumerate(processed_cookies_for_playwright):
                    try:
                        await context.add_cookies([cookie_obj]) 
                        successful_cookies_count += 1
                        print(f"DEBUG: Cookie '{cookie_obj.get('name', 'N/A')}' adicionado com sucesso. ({successful_cookies_count}/{len(processed_cookies_for_playwright)})")
                    except Exception as e:
                        print(f"DEBUG: ERRO ao adicionar cookie '{cookie_obj.get('name', 'N/A')}': {e}")
                        print(f"DEBUG: Cookie problemático: {cookie_obj}")
                
                if successful_cookies_count > 0:
                    print(f"DEBUG: Total de {successful_cookies_count} cookies adicionados com sucesso.")
                    await page.goto("https://www.mercadolivre.com.br/affiliate-program/panel", wait_until="load", timeout=30000)
                    print(f"DEBUG: URL após tentar ir para painel de afiliados com cookies: {page.url}")

                    if "login" not in page.url and "security" not in page.url and "verifica" not in page.url and "seguridad" not in page.url:
                        print("DEBUG: Sessão ativa com cookies.")
                        logged_in = True
                    else:
                        print(f"DEBUG: Cookies inválidos ou expirados. Redirecionado para: {page.url}")
                else:
                    print("DEBUG: Nenhum cookie foi adicionado com sucesso. Pulando para login direto.")
            except json.JSONDecodeError as e:
                print(f"DEBUG: ERRO: Não foi possível decodificar o JSON dos cookies. Verifique o formato no secret. Erro: {e}")
            except Exception as e:
                print(f"DEBUG: Erro geral ao tentar login com cookies: {e}")
        
        # --- Tentar login direto (ML_USERNAME/ML_PASSWORD) se todas as outras falharam ---
        if not logged_in and ml_username and ml_password:
            print("DEBUG: Todas as tentativas de cookies falharam. Tentando login direto com usuário e senha...")
            if not context: # Se o contexto não foi criado antes
                context = await browser.new_context()
                page = await context.new_page()
            logged_in = await perform_ml_login(page, ml_username, ml_password)
        
        if not logged_in:
            print("ERRO FATAL: Não foi possível fazer login no Mercado Livre com NENHUM método (estado da sessão, cookies ou credenciais diretas).")
            print("Por favor, verifique ML_SESSION_STATE, ML_COOKIES_JSON, ML_USERNAME/ML_PASSWORD e desative 2FA se possível.")
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
