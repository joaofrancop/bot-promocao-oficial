    import asyncio
    import pandas as pd
    import os
    import sys 
    from src.affiliate_link_generator import generate_affiliate_links_with_playwright
    from src.telegram_notifier import send_telegram_message 

    # Importações para o scraping do Mercado Livre
    from bs4 import BeautifulSoup
    import requests
    import time as time_sleep_module 
    import re 
    import numpy as np 

    # --- Configurações Iniciais ---
    ML_AFFILIATE_TAG = os.getenv("ML_AFFILIATE_TAG")
    ML_USERNAME = os.getenv("ML_USERNAME") 
    ML_PASSWORD = os.getenv("ML_PASSWORD") 

    # Credenciais do Telegram (mantidas para o futuro, mesmo que não usadas agora)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")     

    # Verificar se a TAG está definida
    if not ML_AFFILIATE_TAG:
        print("ERRO: A TAG de afiliado do Mercado Livre não foi definida. Verifique os GitHub Secrets.")
        sys.exit(1) 

    # Verificar se as credenciais do Telegram estão definidas
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("AVISO: Credenciais do Telegram não definidas. O bot não enviará mensagens para o Telegram.")
        # Não sys.exit(1) aqui, para permitir que o bot continue outras operações

    # --- Constantes para scraping ---
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 60
    SCRAPING_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }

    # --- Funções do scraping original (adaptadas) ---
    def perform_scraping():
        print("Starting web scraping...")
        dados = []
        for i in range(1, 21): 
            url = f'https://www.mercadolivre.com.br/ofertas?page={i}'
            response = None
            for attempt in range(MAX_RETRIES):
                try:
                    response = requests.get(url, headers=SCRAPING_HEADERS, timeout=TIMEOUT_SECONDS)
                    response.raise_for_status()
                    break
                except requests.exceptions.Timeout as e:
                    print(f"Attempt {attempt + 1}/{MAX_RETRIES}: Timeout accessing {url}. Error: {e}")
                    if attempt < MAX_RETRIES - 1:
                        time_sleep_module.sleep(5 * (attempt + 1))
                    else:
                        print(f"All {MAX_RETRIES} attempts failed for {url}.")
                        response = None
                        break
                except requests.exceptions.RequestException as e:
                    print(f"Unexpected request error for {url}: {e}")
                    response = None
                    break

            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                produtos = soup.find_all('div', class_='andes-card poly-card poly-card--grid-card poly-card--large andes-card--flat andes-card--padding-0 andes-card--animated')

                for produto in produtos:
                    imagem_tag = produto.find('img', class_='poly-component__picture')
                    imagem = imagem_tag.get('src') if imagem_tag else None
                    if imagem and imagem.startswith('data:image'):
                        imagem = imagem_tag.get('data-src')

                    nome_tag = produto.find('h3', class_='poly-component__title-wrapper')
                    nome = nome_tag.text if nome_tag else None

                    preco_de = None
                    preco_de_tag = produto.find('s', class_='andes-money-amount andes-money-amount--previous andes-money-amount--cents-comma')
                    if preco_de_tag:
                        fraction_span = preco_de_tag.find('span', class_='andes-money-amount__fraction')
                        cents_span = preco_de_tag.find('span', class_='andes-money-amount__cents')
                        reais_str_raw = fraction_span.get_text(strip=True) if fraction_span else ''
                        centavos_str_raw = cents_span.get_text(strip=True) if cents_span else '00'
                        reais_str = reais_str_raw.replace('.', '').replace(',', '')
                        centavos_str = centavos_str_raw 
                        try:
                            if reais_str or centavos_str != '00':
                                preco_de = float(f"{reais_str}.{centavos_str}")
                            else:
                                preco_de = None
                        except ValueError as e:
                            print(f"DEBUG - ValueError ao converter Preço De: '{reais_str}.{centavos_str}' - Erro: {e}")
                            preco_de = None

                    preco_por = None
                    preco_por_tag = produto.find('span', class_='andes-money-amount andes-money-amount--cents-superscript')
                    if preco_por_tag:
                        fraction_span = preco_por_tag.find('span', class_='andes-money-amount__fraction')
                        cents_span = preco_por_tag.find('span', class_='andes-money-amount__cents')
                        reais_str_raw = fraction_span.get_text(strip=True) if fraction_span else ''
                        centavos_str_raw = cents_span.get_text(strip=True) if cents_span else '00'
                        reais_str = reais_str_raw.replace('.', '').replace(',', '')
                        centavos_str = centavos_str_raw
                        try:
                            if reais_str or centavos_str != '00':
                                preco_por = float(f"{reais_str}.{centavos_str}")
                            else:
                                preco_por = None
                            
                        except ValueError as e:
                            print(f"DEBUG - ValueError ao converter Preço Por: '{reais_str}.{centavos_str}' - Erro: {e}")
                            preco_por = None

                    link_tag = produto.find('a', class_ = 'poly-component__title')
                    link = link_tag.get('href') if link_tag else None

                    span_tag = produto.find('span', class_= 'poly-component__highlight')
                    span_text = span_tag.get_text(strip=True) if span_tag else None

                    parcelas = ''
                    parcelas_tag = produto.find('span', class_='poly-price__installments')
                    if parcelas_tag:
                        full_parcelas_text = parcelas_tag.get_text(separator=' ', strip=True)
                        parcelas = re.sub(r'\\s+', ' ', full_parcelas_text).strip()
                        price_in_installment_tag = parcelas_tag.find('span', class_='andes-money-amount--cents-comma')
                        if price_in_installment_tag and price_in_installment_tag.get('aria-label'):
                            aria_label_installment = price_in_installment_tag.get('aria-label')
                            match_installment = re.search(r'(\\d[\\d\\.,]*)\\s*reales(?:\\s*con\\s*(\\d+)\\s*centavos)?', aria_label_installment)
                            if match_installment:
                                reais_inst = match_installment.group(1).replace('.', '')
                                centavos_inst = match_installment.group(2) if match_installment.group(2) else '00'
                                pass 


                    dados.append({
                        'Imagem': imagem,
                        'Nome': nome,
                        'Preço De': preco_de,
                        'Preço Por': preco_por,
                        'Link': link,
                        'flag': span_text,
                        'Parcelas': parcelas
                        })
            else:
                print(f'Error accessing page {i}: {response.status_code if response else "No response"}')
        
        df = pd.DataFrame(dados)
        print(f"Initial data scraped: {len(df)} products")

        # ETL steps (do código original)
        df = df[df['flag'] == 'MAIS VENDIDO']
        print(f"Data after filtering by 'MAIS VENDIDO' flag: {len(df)} products")

        df['Preço De'] = pd.to_numeric(df['Preço De'], errors='coerce').fillna(0).apply(lambda x: int(np.round(x)))
        df['Preço Por'] = pd.to_numeric(df['Preço Por'], errors='coerce').fillna(0).apply(lambda x: int(np.round(x)))

        df['%_desconto'] = 0.0
        df.loc[(df['Preço De'].notna()) & (df['Preço Por'].notna()) & (df['Preço De'] > 0), '%_desconto'] = \
            ((df['Preço De'] - df['Preço Por']) / df['Preço De'] * 100)
        df['%_desconto'] = df['%_desconto'].fillna(0).astype(int)

        regex_pattern = r'R\$\s*(\d+\.?\d*)\s*,\s*(\d+)'
        replacement_pattern = r'R$\g<1>,\g<2>'
        df['Parcelas'] = df['Parcelas'].str.replace(regex_pattern, replacement_pattern, regex=True)
        
        return df

# --- Função Principal do Bot ---
async def main():
    print("Iniciando o Bot de Ofertas Mercado Livre (Novo Projeto)...")
    
    # 1. Scraping das Ofertas
    products_df = perform_scraping()
    if products_df.empty:
        print("Nenhum produto encontrado após o scraping ou filtro. Encerrando.")
        return

    # 2. Geração de Links de Afiliado com Playwright
    # Passamos os links originais e a TAG para o módulo Playwright
    # ATENÇÃO: Se a geração de links falhar, usaremos os links originais como fallback
    short_links, long_links = await generate_affiliate_links_with_playwright(
        products_df["Link"].tolist(), ML_AFFILIATE_TAG
    )
    
    products_df['short_links'] = short_links
    products_df['long_links'] = long_links 

    # Garantir que short_links e long_links sejam preenchidos mesmo se a geração falhar
    # Usar os links originais se a geração de links de afiliado falhar
    products_df['short_links'] = products_df['short_links'].fillna(products_df['Link'])
    products_df['long_links'] = products_df['long_links'].fillna(products_df['Link'])


    print("\nProdutos processados com links de afiliado (ou originais se falha):")
    print(products_df[['Nome', 'Preço Por', 'short_links']].head())

    # --- NOVO BLOCO PARA SALVAR ARTIFACTS DE DEBUG ---
    # Salva os primeiros 10 produtos raspados para verificar o scraping
    debug_scrape_file = "debug_scraped_products_sample.csv"
    products_df.head(10).to_csv(debug_scrape_file, index=False)
    print(f"DEBUG: Amostra de produtos raspados salva em {debug_scrape_file}")
    # --- FIM NOVO BLOCO ---

    # 3. Filtrar e Preparar para Envio (do código original)
    df_descontos = products_df.sort_values('%_desconto', ascending=False).copy()
    df_preco_por = products_df.sort_values('Preço Por', ascending=True).copy()

    df_descontos['status'] = 'Não enviado'
    df_preco_por['status'] = 'Não enviado'

    # --- Lógica de Envio para Telegram ---
    print("\nIniciando envio de mensagens para o Telegram...")
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        # Enviar produtos com maiores descontos (ex: os 5 primeiros)
        print("Enviando produtos com maiores descontos para o Telegram...")
        for index, row in df_descontos.head(5).iterrows(): # Limitar a 5 para teste
            message_text = (
                f"*{row['Nome']}*\n\n"
                f"~De: R$ {row['Preço De']}~\n"
                f"*Por: R$ {row['Preço Por']}*\n"
                f"{row['%_desconto']}% OFF\n\n"
                f"{row['Parcelas']}\n\n"
                f"Compre aqui: {row['short_links']}"
            )
            response = send_telegram_message(
                TELEGRAM_BOT_TOKEN, 
                TELEGRAM_CHAT_ID, 
                message_text, 
                image_url=row['Imagem'] # Envia a imagem do produto
            )
            if response and response.get('ok'):
                print(f"Mensagem para '{row['Nome']}' enviada com sucesso para o Telegram.")
            else:
                print(f"Falha ao enviar mensagem para '{row['Nome']}' para o Telegram: {response}")
            await asyncio.sleep(2) # Pequeno delay entre mensagens
        
    else:
        print("Credenciais do Telegram não configuradas. Pulando envio para Telegram.")
    # --- Fim Lógica de Envio para Telegram ---

    # (Aqui viria a lógica de Zatten notifier, e Database Manager)
    print("\nDEBUG: Envio para Zatten seria aqui (requer instância de WhatsApp conectada).")
    print("DEBUG: Salvamento do histórico em banco de dados ou CSV seria aqui.")
    
    # Exemplo: Salvar para CSV temporário para verificar
    # products_df.to_csv("products_with_affiliate_links.csv", index=False)
    # print("Produtos com links de afiliado salvos em products_with_affiliate_links.csv")


if __name__ == "__main__":
    asyncio.run(main())
```

**`src/affiliate_link_generator.py`**

```python
import os
import json
import asyncio
import time
from playwright.async_api import async_playwright, Page, BrowserContext, expect

# Função para carregar os cookies do JSON (VERSÃO COM LOGS DE DEBUG E ADIÇÃO INDIVIDUAL)
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
                raw_cookies = json.loads(cookies_json) # Carrega o JSON bruto
                processed_cookies_for_playwright = load_cookies_from_json(cookies_json) # Processa os cookies

                # --- NOVO BLOCO: ADICIONAR COOKIES UM POR UM PARA DEBUG ---
                successful_cookies_count = 0
                for i, cookie_obj in enumerate(processed_cookies_for_playwright):
                    try:
                        await context.add_cookies([cookie_obj]) # Tenta adicionar um cookie por vez
                        successful_cookies_count += 1
                        print(f"DEBUG: Cookie '{cookie_obj.get('name', 'N/A')}' adicionado com sucesso. ({successful_cookies_count}/{len(processed_cookies_for_playwright)})")
                    except Exception as e:
                        print(f"DEBUG: ERRO ao adicionar cookie '{cookie_obj.get('name', 'N/A')}': {e}")
                        print(f"DEBUG: Cookie problemático: {cookie_obj}")
                
                if successful_cookies_count > 0:
                    print(f"DEBUG: Total de {successful_cookies_count} cookies adicionados com sucesso.")
                    # Agora, tente navegar para o painel para verificar a sessão
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
```

**`pipeline.yml`**

```yaml
name: Pipeline Completa de Scrapping e Envio (Novo Bot)

on:
  schedule:
    # Executa a cada 10 minutos (ajuste conforme sua necessidade)
    #- cron: '*/10 * * * *' # Exemplo: a cada 10 minutos
    # Horários específicos podem ser úteis para ofertas
    - cron: '45 9 * * *'  # 06:45 AM BRT
    - cron: '45 11 * * *' # 08:45 AM BRT
    - cron: '45 14 * * *' # 11:45 AM BRT
    - cron: '45 19 * * *' # 04:45 PM BRT
    - cron: '45 22 * * *' # 07:45 PM BRT
      
  workflow_dispatch: # Permite execução manual de toda a pipeline

permissions:
  contents: write # Necessário para commitar o CSV (futuro) ou outros logs
  # Adicione permissão para "actions: write" se for usar actions de upload de artifacts
  # ou se o token GITHUB_TOKEN precisar de mais permissões para o upload-artifact
  actions: write # Adicionado para upload-artifact

jobs:
  full_pipeline:
    runs-on: ubuntu-latest # Ambiente Linux no GitHub Actions

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          ref: main # Checa a branch principal

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11' # Use uma versão recente que o Playwright suporte bem

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          # Instala os navegadores do Playwright
          playwright install --with-deps chromium firefox webkit # --with-deps instala dependências de sistema

      - name: Execute Main Bot Script (main.py)
        run: |
          python main.py
        env:
          # Seus secrets serão passados como variáveis de ambiente para o script Python
          ML_AFFILIATE_TAG: ${{ secrets.ML_AFFILIATE_TAG }}
          ML_COOKIES_JSON: ${{ secrets.ML_COOKIES_JSON }}
          ZATTEN_API_KEY: ${{ secrets.ZATTEN_API_KEY }}
          ZATTEN_PHONE_NUMBER: ${{ secrets.ZATTEN_PHONE_NUMBER }}
          ZATTEN_ATTENDANT_ID: ${{ secrets.ZATTEN_ATTENDANT_ID }}
          # Adicione aqui os secrets para Telegram e OpenAI quando for usá-los
          # TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          # TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          # OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

      # O passo de commit e push do CSV foi removido por ser comentado e pode ter causado problemas
      # Ele será adicionado de volta quando a parte de log estiver no main.py e for ativado.
