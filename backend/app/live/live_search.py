import requests
from duckduckgo_search import DDGS
import traceback
import re

def fetch_live_evidence(query: str):
    try:
        # Cascade search variations for better reach
        print(f"DEBUG: Searching for: '{query}'")
        
        results = []
        variations = [query, f"{query} news 2026", f"{query} fact check"]
        
        with DDGS() as ddgs:
            for v in variations:
                try:
                    results = [r for r in ddgs.text(v, max_results=5)]
                    if results: 
                        print(f"DEBUG: Found {len(results)} results using variation: '{v}'")
                        break
                except: continue

        if not results:
            print("DEBUG: Search failed across all variations")
            return None

        consolidated_text = ". ".join([r.get('body', '') for r in results if r.get('body')])
        top_url = results[0].get('href', 'https://duckduckgo.com') if results else 'https://duckduckgo.com'
        top_title = results[0].get('title', 'Web Results') if results else 'Web Results'
        
        return {
            "source": "Live Internet Search",
            "page": top_title,
            "url": top_url,
            "text": consolidated_text[:3000]
        }
    except Exception as e:
        print(f"DEBUG: Global search error: {e}")
        return None

SEARCH_API = "https://en.wikipedia.org/w/api.php"
SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"

STOP_WORDS = {"a", "an", "the", "with", "on", "in", "of", "and", "is", "at", "by", "for", "to", "it", "her", "his", "their", "my", "your"}

def fetch_wikipedia_evidence(query: str):
    try:
        headers = {"User-Agent": "TruthLensAI/1.0 (educational project)"}
        # Clean query for better search
        clean_query = re.sub(r'[^\w\s]', '', query).lower()
        query_keywords = set(clean_query.split()) - STOP_WORDS
        
        # Try both direct query and more descriptive variations
        variations = [query]
        if len(query_keywords) > 1:
            variations.append(" ".join(list(query_keywords)))
        variations.append(f"{query} history")
        
        for q in variations:
            search_params = {
                "action": "query", "list": "search", "srsearch": q,
                "format": "json", "utf8": 1, "srlimit": 10
            }
            res = requests.get(SEARCH_API, params=search_params, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                search_results = data.get("query", {}).get("search", [])
                
                scored_results = []
                for result in search_results:
                    page_title = result["title"]
                    snippet = result.get("snippet", "").lower()
                    title_keywords = set(re.sub(r'[^\w\s]', '', page_title).lower().split())
                    snippet_keywords = set(re.sub(r'[^\w\s]', r' ', snippet).split())
                    
                    # Calculate overlap score
                    title_overlap = len(query_keywords & title_keywords)
                    snippet_overlap = len(query_keywords & snippet_keywords)
                    score = (title_overlap * 3) + snippet_overlap
                    
                    # Bonus for exact title matches
                    if page_title.lower() in query.lower():
                        score += 5
                    
                    if score > 0 or not query_keywords:
                        scored_results.append((score, page_title))
                
                if scored_results:
                    # Sort by score descending
                    scored_results.sort(key=lambda x: x[0], reverse=True)
                    best_page_title = scored_results[0][1]
                    
                    summary_url = SUMMARY_API + best_page_title.replace(" ", "_")
                    res_sum = requests.get(summary_url, headers=headers, timeout=8)
                    if res_sum.status_code == 200:
                        sum_data = res_sum.json()
                        extract = sum_data.get("extract")
                        page_url = sum_data.get("content_urls", {}).get("desktop", {}).get("page")
                        if extract:
                            return {
                                "source": "Wikipedia", 
                                "page": best_page_title, 
                                "url": page_url or f"https://en.wikipedia.org/wiki/{best_page_title.replace(' ', '_')}",
                                "text": extract[:1500]
                            }
        return None
    except Exception as e:
        print(f"DEBUG: Wikipedia exception: {e}")
        return None
