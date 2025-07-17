import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # ALTE AQUI: de headless=True para headless=False
        browser = await p.chromium.launch(headless=True) # Mude para False para ver o navegador
        page = await browser.new_page()
        print("Navegando para o Mercado Livre...") # Adicione uma mensagem para acompanhar
        await page.goto("https://www.mercadolivre.com.br/")
        print("Página carregada, tentando obter título...") # Adicione outra mensagem
        print(f"Título da página: {await page.title()}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())