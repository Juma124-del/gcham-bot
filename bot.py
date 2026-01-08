import os
import re
import random
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

# Initialize for the 2.0 LITE version (The most reliable free model)
genai.configure(api_key=GOOGLE_API_KEY)

# 'gemini-2.0-flash-lite' is the 2026 workhorse for free accounts
ai_model = genai.GenerativeModel('gemini-2.0-flash-lite')

wp_client = Client(WP_URL, WP_USER, WP_PASS)

def get_trending_usa_topic():
    niches = ["US Economy", "Tech", "Entertainment", "Politics", "Lifestyle"]
    selected = random.choice(niches)
    try:
        response = ai_model.generate_content("One trending USA news headline. Just the headline text.")
        return response.text.strip(), selected
    except Exception as e:
        print(f"❌ Still getting 429? Google may have flagged this key. Error: {e}")
        return None, None

def generate_article(topic, niche):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"Write a professional 1000-word USA news report on: '{topic}'. Use <h1> for title and <h2> for headers. Link to <a href='{base_url}'>GCHAM News</a>."
    response = ai_model.generate_content(prompt)
    return response.text.replace('**', '<b>')

def publish():
    print("🚀 GCHAM: Starting 2.0 Flash-Lite Engine...")
    topic, niche = get_trending_usa_topic()
    
    if not topic:
        print("⚠️ ACTION REQUIRED: This API key is dead. Please use a key from a DIFFERENT Google account.")
        return

    print(f"🔍 Writing: {topic}")
    content = generate_article(topic, niche)
    
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    post = WordPressPost()
    post.title = final_title
    post.content = content
    post.post_status = 'publish'
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', 'Flash-Lite']}
    
    try:
        post_id = wp_client.call(posts.NewPost(post))
        print(f"✅ SUCCESS! GCHAM LIVE: {topic}")
    except Exception as e:
        print(f"❌ WordPress Error: {e}")

if __name__ == "__main__":
    publish()
