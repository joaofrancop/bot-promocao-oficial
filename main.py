import asyncio
import pandas as pd
import os
import sys 
import re 
import numpy as np 
from src.affiliate_link_generator import generate_affiliate_links_with_playwright
from src.telegram_notifier import send_telegram_message # Importa o notifier do Telegram

# Importações para o scraping do Mercado Livre
from bs4 import BeautifulSoup
import requests
import time as time_sleep_module 

# --- Configurações Iniciais ---
ML_AFFILIATE_TAG = os.getenv("ML_AFFILIATE_TAG")
ML_USERNAME = os.getenv("ML_USERNAME") 
ML_PASSWORD = os.getenv("ML_PASSWORD") 

# Credenciais do Telegram
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
    # Condição para enviar: apenas se os secrets do Telegram estiverem configurados
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
