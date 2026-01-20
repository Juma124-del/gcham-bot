import os, json, re, random, requests, logging, time, socket
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from oauth2client.service_account import ServiceAccountCredentials
import httplib2

# ==========================================================
# 🛡️ SECTION 1: SETUP & CONFIGURATION (USA Standards)
# ==========================================================
class Config:
    VERSION = "GCHAM Empire Shield v6.4"
    # 📅 DYNAMIC DATE: Always reflects today's date in 2026
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    BING_KEY = os.getenv("BING_API_KEY")
    WP_URL = os.getenv("WP_URL")
    WP_USER = os.getenv("WP_USER")
    WP_PASS = os.getenv("WP_PASS")
    
    DOMAIN = "gcham.com"
    INDEXING_FOLDER = "INDEXING_SERVICE_JSON"
    
    # Targeting USA Audience (11am Nairobi is 3am EST / Midnight PST)
    USA_AUDIENCE = "USA Professionals, Investors, and News Readers"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
socket.setdefaulttimeout(300)

# ==========================================================
# 🧠 SECTION 2: THE BRAIN (Live & Factual)
# ==========================================================

def get_live_context(niche):
    """Pulls current 2026 facts specifically for GCHAM"""
    tavily = TavilyClient(api_key=Config.TAVILY_KEY)
    query = f"Latest {niche} news headlines USA {Config.CURRENT_DATE} investigative"
    try:
        search_result = tavily.search(query=query, topic="news", days=1, max_results=6)
        context = f"FACTUAL DATA FOR {Config.CURRENT_DATE}:\n"
        for res in search_result['results']:
            context += f"SOURCE: {res['title']}\nFACT: {res['content']}\n\n"
        return context
    except Exception as e:
        return f"Focus on {Config.CURRENT_DATE} economic and political indicators."

# ==========================================================
# ✍️ SECTION 3: THE EDITOR (Google Excerpt Priority)
# ==========================================================

def publish():
    niche = random.choice(["USA Politics", "Economics", "Sports", "Crypto", "Entertainment"])
    live_facts = get_live_context(niche)
    
    # 🎯 SYSTEM INSTRUCTION: Factual, Current, Snippet-First
    system_message = (
        f"You are the Senior Editor at GCHAM. Today is {Config.CURRENT_DATE}. "
        f"Target: {Config.USA_AUDIENCE}. All reports must be 100% FACTUAL. "
        "OUTPUT STRUCTURE: "
        "1. GOOGLE EXCERPT: A 150-character data-rich summary for search snippets. "
        "2. REPORT: 1,500 words with H1-H4 tags. "
        "3. IMAGE KEYWORDS: High-quality keywords (no names). "
        "Format: JSON ONLY. Fields: 'headline', 'google_snippet', 'full_report', 'image_kw'."
    )

    client = Groq(api_key=Config.GROQ_KEY)
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_message}, 
                      {"role": "user", "content": f"Topic: {niche}\nFacts: {live_facts}"}],
            response_format={"type": "json_object"}
        )
        data = json.loads(completion.choices[0].message.content)
        
        # UI/UX: Google Excerpt Box at the beginning
        snippet_html = (
            f"<div style='background:#f9f9f9; padding:20px; border-left:6px solid #d32f2f; margin-bottom:25px; font-style:italic;'>"
            f"<strong>QUICK FACT (Google Excerpt):</strong> {data['google_snippet']}</div>"
        )
        final_content = snippet_html + data['full_report']

        # WordPress Integration
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)
        post = WordPressPost()
        post.title = data['headline']
        post.content = final_content
        post.post_status = 'publish'
        
        post_id = wp.call(posts.NewPost(post))
        
        if post_id:
            full_post = wp.call(posts.GetPost(post_id))
            # Trigger Indexing for USA Traffic
            request_google_indexing(full_post.link)
            request_bing_indexing(full_post.link)

    except Exception as e:
        logging.error(f"❌ Critical Error: {e}")

if __name__ == "__main__":
    publish()
