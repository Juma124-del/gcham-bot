import os
import random
import json
import requests
import logging
import feedparser
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client
from slugify import slugify

# --- CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.getenv("GEMINI_API_KEY") 
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

# Initialize Clients
client = Groq(api_key=GROQ_API_KEY)
wp_client = Client(WP_URL, WP_USER, WP_PASS)

def research_topic(topic):
    """PHASE 1: Research - Fetches real-time facts from Google News RSS."""
    search_query = topic.replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(rss_url)
        # Gather the top 5 snippets to give the AI context
        notes = [f"Source: {e.source.get('title')} - {e.title}" for e in feed.entries[:5]]
        return "\n".join(notes)
    except Exception as e:
        logging.error(f"Research failed: {e}")
        return "No real-time data found. Use general knowledge."

def get_image(search_keyword):
    """PHASE 2: Media - Searches Pexels (High Quality) then Wikimedia (News/Celebs)."""
    # Try Pexels
    if PEXELS_KEY:
        try:
            headers = {"Authorization": PEXELS_KEY}
            url = f"https://api.pexels.com/v1/search?query={search_keyword}&per_page=1"
            res = requests.get(url, headers=headers, timeout=10).json()
            if res.get('photos'):
                return res['photos'][0]['src']['large'], res['photos'][0]['photographer']
        except: pass

    # Fallback to Wikimedia
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"File:{search_keyword}", "gsrlimit": 1, "prop": "imageinfo", "iiprop": "url|user"
    }
    try:
        response = requests.get(url, params=params, timeout=10).json()
        pages = response.get("query", {}).get("pages", {})
        for pgid, data in pages.items():
            info = data["imageinfo"][0]
            return info["url"], info.get("user", "Wikimedia")
    except: return None, None

def generate_content(topic, research_data):
    """PHASE 3: Writing - Uses JSON Mode to ensure perfect formatting."""
    prompt = f"""
    Write a VIRAL and ETHICAL news report about '{topic}'.
    FACTS TO INCLUDE:
    {research_data}

    Format your response as a JSON object with:
    "headline": "...",
    "image_keyword": "one specific noun for image search",
    "excerpt": "short SEO summary",
    "content_html": "full report using <blockquote> for lead, <h3> for FAQs, and <p> for body."
    """
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            temperature=0.7
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        logging.error(f"LLM Error: {e}")
        return None

def publish():
    logging.info("🚀 Starting GCHAM Automated News Desk...")
    
    # 1. Select Niche & Get Trending Topic
    niche = random.choice(["US Economy", "Tech News", "USA Politics", "Entertainment"])
    topic_call = client.chat.completions.create(
        messages=[{"role": "user", "content": f"Give me one trending news headline for {niche}. Title only."}],
        model="llama-3.3-70b-versatile"
    )
    topic = topic_call.choices[0].message.content.strip().replace('"', '')

    # 2. Research & Write
    facts = research_topic(topic)
    data = generate_content(topic, facts)
    if not data: return

    # 3. Handle Images
    img_url, author = get_image(data['image_keyword'])
    
    # 4. Construct WordPress Post
    post = WordPressPost()
    post.title = data['headline']
    post.excerpt = data['excerpt']
    
    final_html = data['content_html']
    
    if img_url:
        try:
            img_res = requests.get(img_url, timeout=15)
            img_upload = {
                'name': f"{slugify(data['headline'])}.jpg",
                'type': 'image/jpeg',
                'bits': xmlrpc_client.Binary(img_res.content)
            }
            res = wp_client.call(media.UploadFile(img_upload))
            post.thumbnail = res['id']
            # Insert professional image block at the top
            img_tag = f'<figure class="wp-block-image"><img src="{res["url"]}" alt="{topic}"/><figcaption>Credit: {author}</figcaption></figure>'
            final_html = img_tag + final_html
        except Exception as e:
            logging.error(f"Image upload failed: {e}")

    post.content = final_html
    post.post_status = 'publish'
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', 'AI News']}

    try:
        post_id = wp_client.call(posts.NewPost(post))
        logging.info(f"✅ PUBLISHED! Post ID: {post_id}")
    except Exception as e:
        logging.error(f"Publishing failed: {e}")

if __name__ == "__main__":
    publish()
