import os, json, re, random, requests, logging, time, socket
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media, GetPost
from wordpress_xmlrpc.compat import xmlrpc_client
from oauth2client.service_account import ServiceAccountCredentials
import httplib2

# --- 1. SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Empire Shield v5.8"
CURRENT_DATE_STR = datetime.now().strftime("%B %d, %Y")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
socket.setdefaulttimeout(300) 

# 🚀 GOOGLE INDEXING (Local Folder)
def request_google_indexing(url):
    folder_path = "INDEXING_SERVICE_JSON"
    try:
        if not os.path.exists(folder_path): return
        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        if not json_files: return
        
        key_file = os.path.join(folder_path, json_files[0])
        scopes = ["https://www.googleapis.com/auth/indexing"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(key_file, scopes=scopes)
        http = creds.authorize(httplib2.Http())
        
        payload = json.dumps({"url": url, "type": "URL_UPDATED"})
        response, result = http.request("https://indexing.googleapis.com/v3/urlNotifications:publish", method="POST", body=payload)
        if response.status == 200: logging.info(f"✅ GOOGLE INDEXED: {url}")
    except Exception as e: logging.error(f"❌ Google Error: {e}")

# 🚀 BING INDEXING (USA Power Move)
def request_bing_indexing(url):
    bing_key = os.getenv("BING_API_KEY") # Store your Bing API key in your environment
    if not bing_key:
        logging.warning("⚠️ Bing Indexing skipped: BING_API_KEY not found.")
        return

    endpoint = "https://www.bing.com/IndexNow"
    data = {
        "host": "worldofvitimbi.com", # Updated to your new name
        "key": bing_key,
        "keyLocation": f"https://worldofvitimbi.com/{bing_key}.txt",
        "urlList": [url]
    }
    try:
        res = requests.post(endpoint, json=data, timeout=15)
        if res.status_code == 200: logging.info(f"🎯 BING INDEXED: {url}")
    except Exception as e: logging.error(f"❌ Bing Error: {e}")

# ... (get_live_context and get_pexels_image functions) ...

def publish():
    # ... (AI Content & WordPress Logic) ...
    try:
        post_id = wp.call(posts.NewPost(post))
        if post_id and post.post_status == "publish":
            full_post = wp.call(posts.GetPost(post_id))
            live_url = full_post.link
            
            # 🔥 DUAL PING STRATEGY
            request_google_indexing(live_url)
            request_bing_indexing(live_url)

    except Exception as e: logging.error(f"❌ Publish Error: {e}")

if __name__ == "__main__":
    publish()
