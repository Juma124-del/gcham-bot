import os
import json
import re
import random
import logging
import feedparser
import requests
import io
import time
from PIL import Image
from groq import Groq
from google.oauth2 import service_account
from googleapiclient.discovery import build
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client
from python_slugify import slugify
from tenacity import retry, stop_after_attempt, wait_fixed # pip install tenacity

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.getenv("GROQ_API_KEY") 
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")
INDEXING_JSON = os.getenv("INDEXING_SERVICE_JSON")

client = Groq(api_key=GROQ_API_KEY)
wp_client = Client(WP_URL, WP_USER, WP_PASS)

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def notify_google_indexing(url):
    if not INDEXING_JSON: return
    try:
        info = json.loads(INDEXING_JSON)
        creds = service_account.Credentials.from_service_account_info(info)
        scoped_creds = creds.with_scopes(["https://www.googleapis.com/auth/indexing"])
        service = build('indexing', 'v3', credentials=scoped_creds)
        service.urlNotifications().publish(body={'url': url, 'type': 'URL_UPDATED'}).execute()
        logging.info(f"🚀 Indexing Notified: {url}")
    except Exception as e:
        logging.error(f"Indexing Retry Failed: {e}")
        raise

def research_topic(topic):
    """Reliable RSS Fetching"""
    search_query = topic.replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"
    try:
        response = requests.get(rss_url, timeout=10)
        feed = feedparser.parse(response.content)
        if not feed.entries: return "No recent news found. Use general historical context."
        return "\n".join([f"- {e.title}" for e in feed.entries[:5]])
    except:
        return "Research server timed out. Using AI general knowledge."

def generate_content(topic, facts):
    prompt = f"""
    Act as a senior USA journalist. Write a viral, ethical news report about '{topic}'.
    STRUCTURE: Inverted Pyramid.
    FACTS: {facts}
    Respond ONLY with JSON: {{"headline":"", "image_keyword":"", "excerpt":"", "content_html":""}}
    """
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        raw = completion.choices[0].message.content
        cleaned = re.sub(r'```json|```', '', raw).strip()
        return json.loads(cleaned)
    except Exception as e:
        logging.error(f"LLM Error: {e}")
        # Fallback Data to prevent crash
        return {
            "headline": topic,
            "image_keyword": "news",
            "excerpt": "Breaking news update regarding recent developments.",
            "content_html": f"<blockquote>Breaking: {topic}</blockquote><p>Details are emerging regarding this developing story...</p>"
        }

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def publish_to_wp(post):
    return wp_client.call(posts.NewPost(post))

def publish():
    logging.info("🚀 GCHAM EXECUTION INITIATED")
    niche = random.choice(["Tech News", "US Economy", "Entertainment", "USA Politics"])
    
    # Get Topic
    try:
        topic_res = client.chat.completions.create(
            messages=[{"role": "user", "content": f"One trending USA headline for {niche}. Just the title."}],
            model="llama-3.3-70b-versatile"
        )
        topic = topic_res.choices[0].message.content.strip().replace('"', '')
    except: return

    facts = research_topic(topic)
    data = generate_content(topic, facts)
    
    post = WordPressPost()
    post.title = data['headline']
    post.content = data['content_html']
    post.excerpt = data['excerpt']
    post.post_status = 'publish'
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', 'Viral']}

    # Media Handling
    if PEXELS_KEY:
        try:
            img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['image_keyword']}&per_page=1", 
                                   headers={"Authorization": PEXELS_KEY}, timeout=10).json()
            if img_res.get('photos'):
                raw_url = img_res['photos'][0]['src']['large']
                img_data = requests.get(raw_url, timeout=10).content
                # Resize
                img = Image.open(io.BytesIO(img_data))
                img.thumbnail((1200, 800))
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85)
                
                up = {'name': f"{slugify(post.title)}.jpg", 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(output.getvalue())}
                res = wp_client.call(media.UploadFile(up))
                post.thumbnail = res['id']
                post.content = f'<figure><img src="{res["url"]}"/></figure>' + post.content
        except Exception as e: logging.error(f"Media Error: {e}")

    # Final Post
    try:
        pid = publish_to_wp(post)
        full_post = wp_client.call(posts.GetPost(pid))
        logging.info(f"✅ GCHAM LIVE: {full_post.link}")
        notify_google_indexing(full_post.link)
    except Exception as e: logging.error(f"Final failure: {e}")

if __name__ == "__main__":
    publish()
