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

genai.configure(api_key=GOOGLE_API_KEY)

# SWITCHED TO 1.5 FLASH TO BYPASS BILLING ERRORS
ai_model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction="You are a veteran USA Investigative Journalist. Your tone is sharp and uses American English."
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
    # Added a try/except here to handle quota issues gracefully
    try:
        topic = ai_model.generate_content(prompt).text.strip()
        return topic, niche
    except Exception as e:
        print(f"Quota error: {e}")
        return None, None

def generate_super_article(topic, niche):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"""Write a 1000-word investigative SEO report on: '{topic}'.
    - Use <h1>, <h2>, <h3>.
    - Start with a TL;DR box.
    - Naturally link to <a href='{base_url}'>GCHAM USA News</a>.
    - End with a 5-question FAQ.
    - Style: High-energy American journalism."""
    return ai_model.generate_content(prompt).text.replace('**', '<b>')

def publish():
    topic, niche = get_trending_usa_topic()
    if not topic: return
    
    print(f"🔍 Topic: {topic}")
    content = generate_super_article(topic, niche)
    
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    img_url = "https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=1200&q=80"
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
