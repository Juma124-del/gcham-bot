import os
import re
import random
import json
import time
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

# Configure with REST for stable connection
genai.configure(api_key=GOOGLE_API_KEY, transport='rest')

# POWERED BY GEMINI 2.0 FLASH (Billing Linked)
MODEL_ID = 'gemini-2.0-flash'
ai_model = genai.GenerativeModel(model_name=MODEL_ID)

wp_client = Client(WP_URL, WP_USER, WP_PASS)

def get_trending_usa_topic():
    categories = ["US Economy", "Silicon Valley Tech", "USA Entertainment", "American Politics", "USA Lifestyle"]
    niche = random.choice(categories)
    prompt = f"Identify the top trending news story in the USA right now for {niche}. Provide the headline only."
    
    try:
        response = ai_model.generate_content(prompt)
        return response.text.strip(), niche
    except Exception as e:
        print(f"🔄 AI Error: {e}")
        return None, None

def generate_super_article(topic, niche):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"""Write a 1200-word investigative SEO report on: '{topic}'.
    - Tone: Sharp, Professional American English.
    - Format: Use <h1> for Title, <h2> and <h3> for subheaders.
    - Include a 'Key Takeaways' box at the start.
    - Naturally link to <a href='{base_url}'>GCHAM News USA</a>.
    - End with a 5-question FAQ section."""
    
    response = ai_model.generate_content(prompt)
    return response.text.replace('**', '<b>').replace('__', '<b>')

def publish():
    print(f"🚀 GCHAM Engine Starting (Model: {MODEL_ID})...")
    topic, niche = get_trending_usa_topic()
    
    if not topic:
        print("❌ Could not fetch topic. Check API Key/Billing.")
        return

    print(f"🔍 Topic Confirmed: {topic}")
    content = generate_super_article(topic, niche)
    
    # Extract <h1> title
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    # Featured News Image
    img_url = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80"
    img_data = requests.get(img_url).content
    media_id = wp_client.call(media.UploadFile({'name': 'news_banner.jpg', 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(img_data)}))['id']

    post = WordPressPost()
    post.title = final_title
    post.content = content
    post.post_status = 'publish'
    post.thumbnail = media_id
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', 'Trending', niche]}
    
    post_id = wp_client.call(posts.NewPost(post))
    final_post = wp_client.call(posts.GetPost(post_id))
    print(f"✅ GCHAM LIVE: {final_post.link}")

if __name__ == "__main__":
    publish()
