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

# --- 1. SECURE CONFIGURATION ---
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")
INDEXING_JSON = os.getenv("INDEXING_SERVICE_ACCOUNT")

# --- 2. AI BRAIN (Stealth & USA Journalism Mode) ---
genai.configure(api_key=GOOGLE_API_KEY)
ai_model = genai.GenerativeModel(
    model_name='gemini-2.0-flash',
    system_instruction="""You are a veteran USA Investigative Journalist. 
    Your style is punchy, high-energy, and uses American English. 
    Never use 'AI' phrases like 'In the digital age'. 
    Focus on facts, controversial angles, and scannable formatting."""
)

wp_client = Client(WP_URL, WP_USER, WP_PASS)

# --- 3. GOOGLE INSTANT INDEXING ---
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
            print(f"🚀 GOOGLE PINGED: {url}")
    except Exception as e:
        print(f"⚠️ Indexing ping skipped (check credentials)")

# --- 4. THE GROWTH ENGINE ---
def get_trending_usa_topic():
    categories = [
        "US Finance (Stocks, Crypto, or Economy)", 
        "Sports (NBA, NFL, or Premier League drama)", 
        "USA Entertainment (Musicians, Hollywood, or TikTok viral)",
        "USA Politics (White House or Congress news)",
        "Health (Longevity, Biotech, or USA Wellness trends)"
    ]
    niche = random.choice(categories)
    prompt = f"Identify the #1 viral, high-volume search news story in the USA right now for {niche}. Provide ONLY the headline."
    topic = ai_model.generate_content(prompt).text.strip()
    return topic, niche

def generate_super_article(topic, niche):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"""Write a 1200-word investigative SEO report on: '{topic}'.
    
    CRITICAL SEO STRUCTURE:
    - Start with an <h1> headline.
    - **TL;DR Summary**: A 50-word fast-fact box at the top.
    - **Internal Link**: Naturally link to <a href='{base_url}'>GCHAM USA News</a> in paragraph 2.
    - **Body**: Use <h2> and <h3> tags. Use <b>bolding</b> for data.
    - **FAQ Section**: End with an <h2> 'Frequently Asked Questions' answering the next 5 logical queries about this topic.
    - **Tone**: American journalism. Varied sentence lengths. 0% AI detection footprint.
    """
    return ai_model.generate_content(prompt).text.replace('**', '<b>')

def generate_social_assets(topic, niche, post_url):
    prompt = f"Based on the topic '{topic}', write a viral Quora Answer (300 words) and a YouTube Shorts Script (60 seconds). Include the link: {post_url}"
    return ai_model.generate_content(prompt).text

# --- 5. THE PUBLISHING PIPELINE ---
def publish():
    topic, niche = get_trending_usa_topic()
    print(f"🔍 Trending in USA: {topic} ({niche})")
    
    content = generate_super_article(topic, niche)
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    # Sourcing a professional image
    img_url = "https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=1200&q=80"
    img_data = requests.get(img_url).content
    media_id = wp_client.call(media.UploadFile({'name': 'usa_news.jpg', 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(img_data)}))['id']

    post = WordPressPost()
    post.title = final_title
    post.content = content
    post.post_status = 'publish'
    post.thumbnail = media_id
    post.terms_names = {'category': [niche.split('(')[0].strip()]}
    
    post_id = wp_client.call(posts.NewPost(post))
    final_post = wp_client.call(posts.GetPost(post_id))
    new_url = final_post.link
    
    print(f"✅ GCHAM LIVE: {new_url}")
    ping_google_indexing(new_url)
    
    # Generate Quora/Social drafts and log them
    social_drafts = generate_social_assets(topic, niche, new_url)
    with open("SOCIAL_PROMO_LOG.md", "a") as f:
        f.write(f"\n\n## {final_title}\n{social_drafts}\n---")

if __name__ == "__main__":
    publish()
