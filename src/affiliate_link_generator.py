import os
import json
import asyncio
import time
from playwright.async_api import async_playwright, Page, BrowserContext

# Função para carregar os cookies do JSON
def load_cookies_from_json(json_string: str) -> list:
    """Converte uma string JSON de cookies em um formato que o Playwright entenda,
    tratando o atributo sameSite e garantindo 'url' ou 'domain'."""
    cookies = json.loads(json_string)

    valid_same_site_values = ["Strict", "Lax", "None"] # Valores aceitos pelo Playwright

    for cookie in cookies:
        # --- CORREÇÃO PARA O ERRO 'Cookie should have either url or domain' ---
        # Se o cookie não tem 'url' e não tem 'domain', ou se 'domain' está vazio/malformado
        if 'url' not in cookie or not cookie['url']: # Se 'url' não existe ou está vazia
            if 'domain' in cookie and cookie['domain']: # Se 'domain' existe e não está vazio
                domain = cookie['domain']
                # Remover o ponto inicial se houver (ex: .mercadolivre.com.br -> mercadolivre.com.br)
                if domain.startswith('.'):
                    domain = domain[1:]
                # Tentar construir a URL. Assume HTTPS e um path padrão se não houver
                path = cookie.get('path', '/') # Pega o path do cookie ou usa '/' como padrão
                cookie['url'] = f"https://{domain}{path}"
            else:
                # Se não tem 'url' e 'domain' também não é útil, use um fallback genérico do ML
                cookie['url'] = "https://www.mercadolivre.com.br/"
        # --- FIM DA CORREÇÃO 'Cookie should have either url or domain' ---

        # --- TRATAMENTO PARA O ERRO sameSite (já feito antes) ---
        if 'sameSite' in cookie:
            if cookie['sameSite'] not in valid_same_site_values or \
               cookie['sameSite'] == "" or \
               cookie['sameSite'] is None: 
                cookie['sameSite'] = "None"
        # --- FIM TRATAMENTO sameSite ---

    return cookies

async def generate_affiliate_links_with_playwright(product_urls: list, affiliate_tag: str):
    """
    Gera links de afiliado do Mercado Livre usando Playwright e cookies de sessão.
    Espera que o secret ML_COOKIES_JSON e ML_AFFILIATE_TAG estejam configurados.
    """
    print("Iniciando geração de links de afiliado com Playwright via cookies...")

    # 1. Obter o JSON de cookies e a TAG do GitHub Secret (ou hardcoded se preferir temporariamente)
    cookies_json = os.getenv("ML_COOKIES_JSON")
    # Se estiver hardcodando temporariamente por teste, remova a linha acima e use:
    # cookies_json = "COLE_A_SUA_STRING_JSON_DE_COOKIES_AQUI" 

    if not cookies_json:
        print("ERRO: O secret ML_COOKIES_JSON não foi definido ou está vazio. Login via cookies falhará.")
        return [None] * len(product_urls), [None] * len(product_urls) # Retorna None para todos os links

    if not affiliate_tag:
        print("ERRO: A TAG de afiliado não foi definida. Os links podem não ser gerados corretamente.")
        # O bot pode continuar, mas os links gerados podem não ter a TAG

    try:
        cookies = load_cookies_from_json(cookies_json)
    except json.JSONDecodeError as e:
        print(f"ERRO: Não foi possível decodificar o JSON dos cookies. Verifique o formato no secret. Erro: {e}")
        return [None] * len(product_urls), [None] * len(product_urls)

    shorts = []
    longs = []
    quantidade_total = 0

    async with async_playwright() as p:
        # Lança o navegador Chromium em modo headless para o GitHub Actions
        # Para testar localmente e VER o navegador, mude headless=True para headless=False
        browser = await p.chromium.launch(headless=True) 

        # Cria um novo contexto para a sessão e carrega os cookies
        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()

        # Tentar navegar para o painel de afiliados (onde a sessão deveria estar ativa)
        print("Tentando acessar o painel de afiliados com cookies...")
        try:
            await page.goto("https://www.mercadolivre.com.br/affiliate-program/panel", wait_until="load", timeout=30000)
            # Verifica se foi redirecionado para login (indicando cookies expirados ou 2FA)
            # Adicionando 'login' e 'seguridad' como verificações
            if "login" in page.url or "security" in page.url or "verifica" in page.url or "seguridad" in page.url:
                print(f"ERRO: Os cookies expiraram, são inválidos ou 2FA ativado. Redirecionado para a página: {page.url}")
                print("Por favor, faça login manual no Mercado Livre, exporte os novos cookies e atualize o secret ML_COOKIES_JSON.")
                await browser.close()
                return [None] * len(product_urls), [None] * len(product_urls)

            print("Sessão aparentemente ativa no painel de afiliados.")
            # Opcional: Aguardar um seletor específico do painel para ter certeza que carregou
            # await page.wait_for_selector('h1:has-text("Painel de Afiliados")', timeout=10000) # Adapte o seletor

        except Exception as e:
            print(f"ERRO na navegação inicial para o painel de afiliados: {e}. Cookies podem estar inválidos.")
            await browser.close()
            return [None] * len(product_urls), [None] * len(product_urls)


        # Lógica para gerar links
        # !!! ATENÇÃO: VOCÊ PRECISA INSPECIONAR O HTML DO SEU PAINEL DE AFILIADOS !!!
        # Os seletores abaixo são exemplos e podem precisar ser ajustados.
        input_url_selector = 'input[name="url"]' # Exemplo: Campo onde cola a URL do produto
        generate_button_selector = 'button[type="submit"]' # Exemplo: Botão para gerar o link

        try:
            await page.wait_for_selector(input_url_selector, timeout=10000) # Espera o campo de input de URL aparecer
            await page.wait_for_selector(generate_button_selector, timeout=10000) # Espera o botão aparecer
        except Exception as e:
            print(f"ERRO: Não foi possível encontrar os seletores do formulário de geração de links. O layout do painel pode ter mudado. Erro: {e}")
            await browser.close()
            return [None] * len(product_urls), [None] * len(product_urls)


        for original_url in product_urls:
            try:
                # Voltar para o painel de afiliados para limpar o formulário e garantir que está na página certa
                await page.goto("https://www.mercadolivre.com.br/affiliate-program/panel", wait_until="load", timeout=30000)
                await page.wait_for_selector(input_url_selector, timeout=10000) # Espera o campo de input carregar novamente

                await page.fill(input_url_selector, original_url)

                # Clicar no botão e interceptar a resposta da API de geração de link
                # A requisição 'createLink' é interceptada para pegar os links gerados
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

            await asyncio.sleep(0.6) # Manter um pequeno delay entre as requisições

        await browser.close()
        return shorts, longs