# agent/tools/browser.py
from playwright.sync_api import sync_playwright

def search_web(query: str) -> str:
    """Search DuckDuckGo using requests and BeautifulSoup with Wikipedia API fallback"""
    import requests
    from bs4 import BeautifulSoup
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Try DuckDuckGo HTML version
    try:
        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        results = []
        for result in soup.select('.result__snippet')[:5]:
            text = result.get_text(strip=True)
            if text and len(text) > 30:
                results.append(text)
        if results:
            return '\n\n'.join(f"{i+1}. {res}" 
                               for i, res in enumerate(results))
    except Exception:
        pass
    
    # Fallback: Wikipedia API
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if 'extract' in data:
            return f"Wikipedia: {data['extract'][:1500]}"
    except Exception:
        pass
    
    return f"Search unavailable. Using built-in knowledge for: {query}"

def scrape_page(url: str) -> str:
    """Open a URL and return its main text content"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state('networkidle')
            
            # Clean page: remove scripts, styles, nav, footer, etc.
            page.evaluate("""() => {
                const elements = document.querySelectorAll('script, style, header, footer, nav, iframe, noscript');
                elements.forEach(el => el.remove());
            }""")
            
            text = page.locator("body").inner_text()
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = "\n".join(lines)
            
            browser.close()
            return clean_text[:3000]
    except Exception as e:
        return f"Error scraping page: {str(e)}"
