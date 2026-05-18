#news_connector.py

from configs import Config
from together import Together
import re
import requests
from urllib.parse import urlparse
from newspaper import Article
import json
from pathlib import Path

class BraveNewsAnalyst:
    # Constants moved inside the class
    PAYWALLED_DOMAINS = {'wsj.com', 'ft.com', 'bloomberg.com', 'nytimes.com', 'economist.com'}
    
    DEFAULT_KEYWORDS = [
        "forecast", "guidance", "sales", "earnings", "profit", "revenue", 
        "valuation", "growth", "regulatory", "debt", "analysts", 
        "competition", "supply chain", "expansion", "layoffs",
        "executive changes", "product launch", "cash flow", "CEO"
    ]

    def __init__(self, client: Together, model: str = Config.DEFAULT_MODEL):
        self.llm_client = client
        self.brave_api_key = Config.BRAVE_API_KEY
        self.model = model
        self.system_prompt = "You are tasked to summarize news to no more than 200 words. Do not include a title."

    # --- Internal Helpers (Preceded by _) ---

    def _build_query(self, company, ticker):
        company_query = f"('{company}'" + (f" OR '{ticker}'" if ticker else "") + ")"
        keyword_clause = " OR ".join(self.DEFAULT_KEYWORDS)
        return f"{company_query} AND ({keyword_clause})"

    def _get_search_results(self, query, count=5):
        encoded_query = requests.utils.quote(query)
        goggle_url = "https://gist.githubusercontent.com/medlum/acd4fcb37229a7f589510794a29eeb1d/raw/8f2cffa544692eb0f69a763c5b9c04fbefbe4bff/trusted-financial-news.goggle"
        encoded_goggle = requests.utils.quote(goggle_url)
        
        url = (f"https://api.search.brave.com/res/v1/news/search"
               f"?q={encoded_query}&count={count}&freshness=p30d&goggles={encoded_goggle}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "X-Subscription-Token": self.brave_api_key
        }
        
        response = requests.get(url, headers=headers)
        return response.json().get("results", [])

    def _extract_text(self, url):
        domain = urlparse(url).netloc
        if any(pw in domain for pw in self.PAYWALLED_DOMAINS):
            return None
            
        try:
            article = Article(url)
            article.download()
            article.parse()
            return article.text.strip() if len(article.text.strip()) > 200 else None
        except:
            return None

    def _is_relevant(self, title, clean_company, symbol_lower):
        suffix_pattern = re.compile(r"\b(inc|corp|ltd|co|incorporated|corporation)\b\.?", re.I)
        cleaned_title = suffix_pattern.sub("", title).lower()
        return clean_company in cleaned_title or symbol_lower in title.lower()

    # --- Core Logic Methods ---

    def summarize_text(self, text):
        if not text: return ""
        
        collected_response = ""
        stream = self.llm_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.2,
            stream=True,
        )

        for chunk in stream:
            if hasattr(chunk, "choices") and chunk.choices:
                content = chunk.choices[0].delta.content or ""
                collected_response += content
        return collected_response

    def fetch_company_news(self, company, symbol, max_results=5):
        # Use the cleaned name provided by the Agent
        query = self._build_query(company, symbol)
        raw_results = self._get_search_results(query, count=10)
        
        # Simple regex to strip legal suffixes for more flexible relevance matching
        clean_co = re.sub(r"\b(inc|corp|ltd|co|corporation)\b\.?", "", company, flags=re.I).strip().lower()

        sorted_news = sorted(
            [n for n in raw_results if n.get("type") == "news_result"],
            key=lambda x: x.get("page_age", ""), # Brave usually returns ISO strings here
            reverse=True
        )

        final_news = []
        for news in sorted_news:
            if len(final_news) >= max_results: break
            
            # Verify result is actually about our company
            title = news.get('title', '').lower()
            if clean_co not in title and symbol.lower() not in title:
                continue
                
            print(f"Processing: {news['title'][:50]}...")
            article_content = self._extract_text(news['url'])
            
            if article_content:
                summary = self.summarize_text(article_content)
                final_news.append({
                    "title": news["title"],
                    "date": news.get("page_age"),
                    "summary": summary,
                    "url": news["url"]
                })
        
        return final_news
    
