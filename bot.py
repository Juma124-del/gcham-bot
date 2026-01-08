import os
import re
import random
import json
import requests
import google.generativeai as genai
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import media, posts
from wordpress_xmlrpc.compat import xmlrpc_client
from oauth2client.service_account import ServiceAccountCredentials
import httplib2

# --- CONFIGURATION ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")
INDEXING_JSON = os.getenv("INDEXING_SERVICE_ACCOUNT")

# FORCE STABLE API VERSION
genai.configure(api_key=GOOGLE_API_KEY, transport='rest')

# USE THE STABLE MODEL ALIAS
ai_model = genai.GenerativeModel(
    model_name='gemini-1.5-flash'
)

wp_client = Client(WP_URL, WP_USER, WP_PASS)

def ping_google_indexing(url):
    try:
        scopes = ["https://www.googleapis.com/auth/indexing"]
        endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
        service_account_info = json.loads(INDEXING_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scopes=scopes)
        http = creds.authorize(httplib2.Http())
        content = json.dumps({"url": url, "type": "URL_UPDATED"})
        response, resp_content = http.request(endpoint, method="POST", body=content)
        if response.status == 200:
            print(f"🚀 Indexed: {url}")
    except Exception:
        print(f"⚠️ Indexing ping skipped")

def get_trending_usa_topic():
    categories = ["US Finance", "US Sports", "USA Entertainment", "USA Politics", "USA Health"]
    niche = random.choice(categories)
    prompt = f"Identify the #1 trending news story in the USA right now for {niche}. Headline only."
    try:
        # Explicitly using the stable model call
        response = ai_model.generate_content(prompt)
        return response.text.strip(), niche
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return None, None

def generate_super_article(topic, niche):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"Write a 1000-word investigative SEO report on: '{topic}'. Use <h1>, <h2>, <h3>. Start with a TL;DR box. Naturally link to <a href='{base_url}'>GCHAM USA News</a>. High-energy American journalism."
    response = ai_model.generate_content(prompt)
    return response.text.replace('**', '<b>')

def publish():
    topic, niche = get_trending_usa_topic()
    if not topic: return
    
    print(f"🔍 Researching: {topic}")
    content = generate_super_article(topic, niche)
    
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    # Professional Stock Image for USA News
    img_url = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80"
    img_data = requests.get(img_url).content
    media_id = wp_client.call(media.UploadFile({'name': 'news.jpg', 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(img_data)}))['id']

    post = WordPressPost()
    post.title = final_title
    post.content = content
    post.post_status = 'publish'
    post.thumbnail = media_id
    
    post_id = wp_client.call(posts.NewPost(post))
    final_post = wp_client.call(posts.GetPost(post_id))
    print(f"✅ GCHAM LIVE: {final_post.link}")
    ping_google_indexing(final_post.link)

if __name__ == "__main__":
    publish()
