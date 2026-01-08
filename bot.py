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

# Initialize specifically for Gemini 2.0
genai.configure(api_key=GOOGLE_API_KEY)

# Using the exact 2026 model string for Gemini 2
ai_model = genai.GenerativeModel('gemini-2.0-flash')

wp_client = Client(WP_URL, WP_USER, WP_PASS)

def get_trending_usa_topic():
    niches = ["US Economy", "Silicon Valley Tech", "USA Entertainment", "American Politics", "USA Lifestyle"]
    selected = random.choice(niches)
    try:
        # Standard generate_content call for Gemini 2
        response = ai_model.generate_content(f"Top trending news headline in {selected} for USA today. Text only.")
        return response.text.strip(), selected
    except Exception as e:
        print(f"❌ Gemini 2 Quota/Connection Error: {e}")
        return None, None

def generate_article(topic, niche):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"""Write a 1200-word investigative report on: '{topic}'.
    - Use <h1> for the title.
    - Use <h2> for subheadings.
    - Professional USA Journalism tone.
    - Link to <a href='{base_url}'>GCHAM News</a>."""
    
    response = ai_model.generate_content(prompt)
    return response.text.replace('**', '<b>')

def publish():
    print("🚀 GCHAM: Launching Gemini 2.0 Engine...")
    topic, niche = get_trending_usa_topic()
    
    if not topic: return

    print(f"🔍 Topic: {topic}")
    content = generate_article(topic, niche)
    
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    post = WordPressPost()
    post.title = final_title
    post.content = content
    post.post_status = 'publish'
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', 'Gemini 2.0']}
    
    try:
        post_id = wp_client.call(posts.NewPost(post))
        final_post = wp_client.call(posts.GetPost(post_id))
        print(f"✅ SUCCESS! GCHAM LIVE: {final_post.link}")
    except Exception as e:
        print(f"❌ WordPress Error: {e}")

if __name__ == "__main__":
    publish()
