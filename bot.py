import os, json, re, random, requests, logging, time, socket
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from oauth2client.service_account import ServiceAccountCredentials
import httplib2

# ==========================================================
# 🛡️ SECTION 1: SETUP (USA Professional Standards)
# ==========================================================
class Config:
    VERSION = "GCHAM Empire Shield v6.5"
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    WP_URL = os.getenv("WP_URL")
    WP_USER = os.getenv("WP_USER")
    WP_PASS = os.getenv("WP_PASS")
    BING_KEY = os.getenv("BING_API_KEY")
    DOMAIN = "gcham.com"
    INDEXING_FOLDER = "INDEXING_SERVICE_JSON"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
socket.setdefaulttimeout(300)

# ==========================================================
# 🧠 SECTION 2: FACT-GATHERING (Retains Truth)
# ==========================================================

def get_live_context(niche):
    """Pulls deep context to prevent hallucinations"""
    tavily = TavilyClient(api_key=Config.TAVILY_KEY)
    # Increased max_results to 10 for more factual "meat" to write 1500 words
    query = f"USA {niche} news {Config.CURRENT_DATE} in-depth analysis"
    try:
        search_result = tavily.search(query=query, topic="news", days=1, max_results=10)
        context = f"STRICT FACTUAL DATA FOR {Config.CURRENT_DATE}:\n"
        for res in search_result['results']:
            context += f"SOURCE: {res['title']}\nCONTENT: {res['content']}\n\n"
        return context
    except Exception as e:
        return "Focus on established 2026 economic trends."

# ==========================================================
# ✍️ SECTION 3: THE EDITOR (The 1,500 Word Logic)
# ==========================================================

def publish():
    niche = random.choice(["USA Politics", "Economics", "Sports", "Crypto", "Entertainment"])
    live_facts = get_live_context(niche)
    
    client = Groq(api_key=Config.GROQ_KEY)
    
    # 🎯 SYSTEM PROMPT: Forces length and strict adherence to facts
    system_message = (
        f"You are the Lead Investigative Journalist at GCHAM. Today is {Config.CURRENT_DATE}. "
        "Your goal is a 1,500-word deep-dive report. "
        "STRICT RULES: "
        "1. NO HALLUCINATIONS: Use ONLY the facts provided. If a detail is not in the facts, do not invent it. "
        "2. WORD COUNT: You must write a minimum of 1,200 words. Expand on the 'Why' and 'Impact' of each fact. "
        "3. STRUCTURE: Use H1 for the title, a <div> for a 'Google Excerpt', followed by H2 and H3 subheadings. "
        "4. TONE: Professional, USA-centric, investigative. "
        "Format: JSON ONLY. Fields: 'headline', 'google_snippet', 'full_report'."
    )

    try:
        # Step 1: Generate the high-volume factual content
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_message}, 
                {"role": "user", "content": f"Topic: {niche}\nFACTS TO EXPAND: {live_facts}"}
            ],
            temperature=0.3, # Lower temperature = Less hallucination
            response_format={"type": "json_object"}
        )
        data = json.loads(completion.choices[0].message.content)
        
        # UI Styling for the Snippet
        snippet_html = (
            f"<div style='background:#f1f1f1; padding:25px; border-left:8px solid #004a99; margin-bottom:30px;'>"
            f"<strong>USA NEWS BRIEF (GCHAM EXCERPT):</strong> {data['google_snippet']}</div>"
        )
        
        # Combine content
        final_body = snippet_html + data['full_report']

        # WordPress Post
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)
        post = WordPressPost()
        post.title = data['headline']
        post.content = final_body
        post.post_status = 'publish'
        
        post_id = wp.call(posts.NewPost(post))
        logging.info(f"🚀 GCHAM Live: {post_id}")

    except Exception as e:
        logging.error(f"❌ Engine Error: {e}")

if __name__ == "__main__":
    publish()
