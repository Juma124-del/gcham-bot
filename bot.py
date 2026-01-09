import os
import random
import json
import requests
import logging
import feedparser
import httplib2
from groq import Groq
from oauth2client.service_account import ServiceAccountCredentials
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client
from python_slugify import slugify

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Credentials from GitHub Secrets
GROQ_API_KEY = os.getenv("GEMINI_API_KEY") 
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")
INDEXING_SERVICE_JSON = os.getenv("INDEXING_SERVICE_JSON") # The JSON string from Google

client = Groq(api_key=GROQ_API_KEY)
wp_client = Client(WP_URL, WP_USER, WP_PASS)

def notify_google_indexing(url):
    """PHASE 0: Indexing - Tells Google to crawl the new post immediately."""
    if not INDEXING_SERVICE_JSON:
        logging.warning("Indexing JSON not found. Skipping.")
        return
    
    try:
        scopes = ["https://www.googleapis.com/auth/indexing"]
        key_data = json.loads(INDEXING_SERVICE_JSON)
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(key_data, scopes=scopes)
        http = credentials.authorize(httplib2.Http())
        
        endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
        content = json.dumps({"url": url, "type": "URL_UPDATED"})
        
        response, content = http.request(endpoint, method="POST", body=content)
        if response.status == 200:
            logging.info(f"🚀 Google Indexing Notified for: {url}")
        else:
            logging.error(f"Indexing API Error {response.status}: {content}")
    except Exception as e:
        logging.error(f"Indexing Failed: {e}")

def research_topic(topic):
    """PHASE 1: Research - Gets real-time facts."""
    search_query = topic.replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)
    notes = [f"Source: {e.source.get('title')} - {e.title}" for e in feed.entries[:5]]
    return "\n".join(notes)

def get_image(search_keyword):
    """PHASE 2: Media - Pexels or Wikimedia."""
    if PEXELS_KEY:
        try:
            headers = {"Authorization": PEXELS_KEY}
            url = f"https://api.pexels.com/v1/search?query={search_keyword}&per_page=1"
            res = requests.get(url, headers=headers, timeout=10).json()
            if res.get('photos'):
                return res['photos'][0]['src']['large'], res['photos'][0]['photographer']
        except: pass

    # Wikimedia Fallback
    url = "https://commons.wikimedia.org/w/api.php"
    params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"File:{search_keyword}", "gsrlimit": 1, "prop": "imageinfo", "iiprop": "url|user"}
    try:
        response = requests.get(url, params=params, timeout=10).json()
        pages = response.get("query", {}).get("pages", {})
        for pgid, data in pages.items():
            info = data["imageinfo"][0]
            return info["url"], info.get("user", "Wikimedia")
    except: return None, None

def generate_content(topic, research_data):
    """PHASE 3: Writing - Structured JSON output."""
    prompt = f"Write a viral news report about '{topic}'. Facts: {research_data}. Respond ONLY with a JSON object containing: 'headline', 'image_keyword', 'excerpt', and 'content_html' (use <blockquote> for lead)."
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logging.error(f"LLM Error: {e}"); return None

def publish():
    logging.info("🚀 GCHAM EXECUTION STARTED")
    
    # 1. Topic & Research
    niche = random.choice(["US Economy", "Tech News", "USA Politics"])
    topic_call = client.chat.completions.create(messages=[{"role": "user", "content": f"Trending news headline for {niche}. Title only."}], model="llama-3.3-70b-versatile")
    topic = topic_call.choices[0].message.content.strip().replace('"', '')
    facts = research_topic(topic)
    
    # 2. Write & Media
    data = generate_content(topic, facts)
    if not data: return
    img_url, author = get_image(data['image_keyword'])
    
    # 3. WordPress Setup
    post = WordPressPost()
    post.title = data['headline']
    post.excerpt = data['excerpt']
    post.post_status = 'publish'
    post.terms_names = {'category': [niche], 'post_tag': ['News', 'Automated']}
    
    final_html = data['content_html']
    if img_url:
        try:
            img_res = requests.get(img_url, timeout=15)
            img_data = {'name': f"{slugify(data['headline'])}.jpg", 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(img_res.content)}
            res = wp_client.call(media.UploadFile(img_data))
            post.thumbnail = res['id']
            img_tag = f'<figure><img src="{res["url"]}" alt="{topic}"/><figcaption>Credit: {author}</figcaption></figure>'
            final_html = img_tag + final_html
        except: pass

    post.content = final_html

    # 4. Final Push
    try:
        post_id = wp_client.call(posts.NewPost(post))
        full_post = wp_client.call(posts.GetPost(post_id))
        logging.info(f"✅ Live at: {full_post.link}")
        
        # Notify Google Indexing API
        notify_google_indexing(full_post.link)
        
    except Exception as e:
        logging.error(f"Final failure: {e}")

if __name__ == "__main__":
    publish()
