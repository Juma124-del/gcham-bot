import os
import re
import random
import time
import requests
import google.generativeai as genai
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import media, posts
from wordpress_xmlrpc.compat import xmlrpc_client

# --- CONFIGURATION ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")

# Initialize Gemini 1.5 with professional journalism instructions
genai.configure(api_key=GOOGLE_API_KEY)
ai_model = genai.GenerativeModel(
    model_name='gemini-1.5-flash-8b',
    system_instruction="You are a senior USA investigative journalist. Write in a professional, engaging tone for a North American audience. Focus on SEO-rich headlines and structured content."
)

wp_client = Client(WP_URL, WP_USER, WP_PASS)

def get_trending_usa_topic():
    niches = ["US Finance", "Silicon Valley Tech", "USA Entertainment", "American Politics", "USA Health"]
    selected = random.choice(niches)
    try:
        response = ai_model.generate_content(f"Provide one high-traffic trending news headline in {selected} for today. Just the headline.")
        return response.text.strip(), selected
    except Exception as e:
        print(f"❌ API still syncing: {e}")
        return None, None

def generate_article(topic, niche):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"""Write a 1200-word viral news report on: '{topic}'.
    1. Start with a <h1> headline.
    2. Use <h2> for subheadings.
    3. Include a 'Why This Matters' summary box.
    4. Link to <a href='{base_url}'>GCHAM USA News</a>.
    5. End with 5 FAQs for Google Search SEO."""
    
    response = ai_model.generate_content(prompt)
    return response.text.replace('**', '<b>').replace('__', '<b>')

def publish():
    print("🚀 GCHAM Engine: Initializing...")
    topic, niche = get_trending_usa_topic()
    
    if not topic:
        print("⚠️ Waiting for Google Billing Sync (Limit: 0). Try a NEW API Key in AI Studio.")
        return

    print(f"🔍 Writing for Niche [{niche}]: {topic}")
    content = generate_article(topic, niche)
    
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    # Professional News Banner
    img_url = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80"
    img_data = requests.get(img_url).content
    media_id = wp_client.call(media.UploadFile({'name': 'news.jpg', 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(img_data)}))['id']

    post = WordPressPost()
    post.title = final_title
    post.content = content
    post.post_status = 'publish'
    post.thumbnail = media_id
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', 'Trending']}
    
    post_id = wp_client.call(posts.NewPost(post))
    final_post = wp_client.call(posts.GetPost(post_id))
    print(f"✅ GCHAM LIVE: {final_post.link}")

if __name__ == "__main__":
    publish()
