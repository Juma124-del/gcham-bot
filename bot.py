import os
import re
import time
import requests
import google.generativeai as genai
from datetime import datetime
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import media, posts
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. CONFIGURATION (Pulling from GitHub Secrets) ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")

genai.configure(api_key=GOOGLE_API_KEY)
# Using Gemini 2.5 Flash-Lite: The most efficient model for 2026 automation
ai_model = genai.GenerativeModel('gemini-2.5-flash-lite')
wp_client = Client(WP_URL, WP_USER, WP_PASS)

def get_trending_news():
    """Instructs AI to simulate a news crawler and pick a hot USA topic."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    prompt = f"""
    Current Time: {current_time}. 
    Identify the #1 trending topic in the USA right now regarding 'Premier League Football' or 'Generative AI Tech'.
    Provide only the headline for an article that would go viral on Google Discover.
    """
    response = ai_model.generate_content(prompt)
    return response.text.strip()

def generate_article(topic):
    """Writes a professional, high-end SEO article."""
    prompt = f"""
    Write a 1,000-word deep-dive professional article.
    TOPIC: {topic}
    TARGET: USA Audience, Google Discover.
    
    STRUCTURE:
    - <h1> headline.
    - <blockquote> 'Executive Summary' for AI snippets.
    - <h2>, <h3> subheadings for scannability.
    - Professional, analytical, and slightly sensational tone (No clickbait).
    - Use HTML tags (<b>, <i>, <ul>). NO markdown stars (**).
    - End with: 'Analysis by the GCHAM Global News Desk.'
    """
    response = ai_model.generate_content(prompt)
    return response.text.replace('**', '<b>').replace('*', '')

def publish():
    print("🕵️ Finding trending news for GCHAM...")
    topic = get_trending_news()
    
    print(f"✍️ Writing high-end article: {topic}")
    content = generate_article(topic)
    
    # Extracting title from first <h1> if available
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    # 2. SOURCE THE 1200PX IMAGE (Requirement for USA Discover)
    print("📸 Fetching high-resolution visual...")
    # Using a high-quality dynamic image source (Unsplash API placeholder)
    img_url = "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=1200&q=80"
    img_data = requests.get(img_url).content
    
    data = {
        'name': f'gcham_news_{int(time.time())}.jpg',
        'type': 'image/jpeg',
        'bits': xmlrpc_client.Binary(img_data)
    }
    media_id = wp_client.call(media.UploadFile(data))['id']

    # 3. POST TO WORDPRESS
    print("🚀 Executing Post to GCHAM.com...")
    post = WordPressPost()
    post.title = final_title
    post.content = content
    post.post_status = 'publish'
    post.thumbnail = media_id
    post.terms_names = {'category': ['Trending', 'Insights']}
    
    wp_client.call(posts.NewPost(post))
    print(f"✅ GCHAM UPDATED: {final_title}")

if __name__ == "__main__":
    publish()
