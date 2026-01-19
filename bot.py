import os, json, re, random, requests, logging, time, socket
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media # Cleaned Import
from wordpress_xmlrpc.compat import xmlrpc_client
from oauth2client.service_account import ServiceAccountCredentials
import httplib2

# ==========================================================
# 🛡️ SECTION 1: SETUP & CONFIGURATION LOGIC (The Settings)
# ==========================================================
class Config:
    VERSION = "World of Vitimbi Shield v6.0"
    # 📅 Live Date Logic: Ensures bot is always today
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    
    # API Credentials (USA Target)
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    BING_KEY = os.getenv("BING_API_KEY") # For IndexNow USA
    
    # WordPress Settings
    WP_URL = os.getenv("WP_URL")
    WP_USER = os.getenv("WP_USER")
    WP_PASS = os.getenv("WP_PASS")
    
    # Path Logic
    INDEXING_FOLDER = "INDEXING_SERVICE_JSON"
    
    # Safety Settings
    TIMEOUT = 300
    NICHE_PROFILES = {
        "USA Politics": "draft", "Economics": "draft",
        "Sports": "publish", "Crypto": "publish", "Entertainment": "publish"
    }

# Apply Setup
socket.setdefaulttimeout(Config.TIMEOUT)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================================
# 🧠 SECTION 2: FUNCTIONAL LOGIC (The Brain)
# ==========================================================

def get_live_context(niche):
    """Gathers real-time 2026 data using Tavily"""
    if not Config.TAVILY_KEY: return f"Focus on {Config.CURRENT_DATE} USA trends."
    tavily = TavilyClient(api_key=Config.TAVILY_KEY)
    query = f"Latest {niche} news headlines USA {Config.CURRENT_DATE} investigative"
    try:
        search_result = tavily.search(query=query, topic="news", days=1, max_results=5)
        context = f"REAL-TIME CONTEXT FOR {Config.CURRENT_DATE}:\n"
        for result in search_result['results']:
            context += f"- {result['title']}: {result['content']}\n"
        return context
    except Exception as e:
        logging.error(f"❌ Context Error: {e}")
        return f"Focus on {Config.CURRENT_DATE} industry technicals."

# ==========================================================
# 🚀 SECTION 3: INDEXING LOGIC (Google & Bing USA)
# ==========================================================

def request_google_indexing(url):
    """Finds Google JSON key and pings API"""
    try:
        if not os.path.exists(Config.INDEXING_FOLDER): return
        json_files = [f for f in os.listdir(Config.INDEXING_FOLDER) if f.endswith('.json')]
        if not json_files: return
        
        key_file = os.path.join(Config.INDEXING_FOLDER, json_files[0])
        scopes = ["https://www.googleapis.com/auth/indexing"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(key_file, scopes=scopes)
        http = creds.authorize(httplib2.Http())
        
        payload = json.dumps({"url": url, "type": "URL_UPDATED"})
        response, result = http.request("https://indexing.googleapis.com/v3/urlNotifications:publish", method="POST", body=payload)
        if response.status == 200: logging.info(f"✅ GOOGLE INDEXED: {url}")
    except Exception as e: logging.error(f"❌ Google Indexing Failed: {e}")

def request_bing_indexing(url):
    """Pings Bing IndexNow for USA workplace audience"""
    if not Config.BING_KEY: return
    endpoint = "https://www.bing.com/IndexNow"
    data = {
        "host": "worldofvitimbi.com",
        "key": Config.BING_KEY,
        "keyLocation": f"https://worldofvitimbi.com/{Config.BING_KEY}.txt",
        "urlList": [url]
    }
    try:
        res = requests.post(endpoint, json=data, timeout=15)
        if res.status_code == 200: logging.info(f"🎯 BING INDEXED: {url}")
    except Exception as e: logging.error(f"❌ Bing Indexing Failed: {e}")

# ==========================================================
# ✍️ SECTION 4: PUBLISHING LOGIC (The Editor)
# ==========================================================

def publish():
    if not all([Config.GROQ_KEY, Config.WP_URL]):
        logging.error("❌ Setup Logic Error: Missing API Keys.")
        return

    niche = random.choice(list(Config.NICHE_PROFILES.keys()))
    live_facts = get_live_context(niche)
    
    # Senior Editor Persona
    system_message = (
        f"You are the Senior Editor for World of Vitimbi. Write 1,500 words. "
        f"Date: {Config.CURRENT_DATE}. Focus on USA audience needs. "
        "Strict SEO, professional H1-H4 tags. Do NOT use person names for image keywords."
    )

    client = Groq(api_key=Config.GROQ_KEY)
    
    try:
        # 1. Content Generation
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": f"Topic: {niche}\nFacts: {live_facts}"}],
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        # 2. Post Assembly (Simplified for brevity)
        post = WordPressPost()
        post.title = data.get('headline')
        post.content = data.get('body_html')
        post.post_status = Config.NICHE_PROFILES[niche]
        
        # 3. WordPress Publish
        post_id = wp.call(posts.NewPost(post))
        
        # 4. Trigger Indexing for Published Articles
        if post_id and post.post_status == "publish":
            full_post = wp.call(posts.GetPost(post_id))
            live_url = full_post.link
            request_google_indexing(live_url)
            request_bing_indexing(live_url)

    except Exception as e: logging.error(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    publish()
