import os
import re
import random
import requests
import google.generativeai as genai
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import media, posts
from wordpress_xmlrpc.compat import xmlrpc_client

# --- CONFIGURATION ---
# Use the NEW API KEY you found in your other Google account
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY") 
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")

# Initialize Gemini 1.5 Flash - The best "Free" engine for 2026
genai.configure(api_key=GOOGLE_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

wp_client = Client(WP_URL, WP_USER, WP_PASS)

def get_trending_usa_topic():
    niches = ["US Finance", "Silicon Valley Tech", "USA Entertainment", "American Politics", "USA Health"]
    selected = random.choice(niches)
    try:
        # Simple prompt to test if the key actually works
        response = ai_model.generate_content(f"Top 1 trending news headline in {selected} for USA today. Just the text.")
        return response.text.strip(), selected
    except Exception as e:
        print(f"❌ Account Error: This key also has no quota. Error: {e}")
        return None, None

def generate_article(topic, niche):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"""Write a 1000-word viral news report for GCHAM.com about: '{topic}'.
    - Use <h1> for the title.
    - Use <h2> for at least 3 subheadings.
    - Use <b> for emphasis.
    - Link to <a href='{base_url}'>GCHAM News</a>.
    - Professional, energetic American journalism style."""
    
    response = ai_model.generate_content(prompt)
    return response.text.replace('**', '<b>')

def publish():
    print("🚀 GCHAM: Testing New Account Key...")
    topic, niche = get_trending_usa_topic()
    
    if not topic: return

    print(f"🔍 Article Topic: {topic}")
    content = generate_article(topic, niche)
    
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    # Set up the post
    post = WordPressPost()
    post.title = final_title
    post.content = content
    post.post_status = 'publish'
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', 'Trending']}
    
    # Optional: If you have an image URL, you can add it here.
    # Keeping it simple for the first 'Account Test' run.
    
    try:
        post_id = wp_client.call(posts.NewPost(post))
        final_post = wp_client.call(posts.GetPost(post_id))
        print(f"✅ SUCCESS! GCHAM LIVE: {final_post.link}")
    except Exception as e:
        print(f"❌ WordPress Error: {e}")

if __name__ == "__main__":
    publish()
