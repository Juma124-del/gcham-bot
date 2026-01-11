import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  # New: Search Engine for AI
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Final Shield v4.3"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_live_context(niche):
    """Fetches real-time 2026 facts so the bot doesn't hallucinate"""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        logging.warning("⚠️ No TAVILY_API_KEY found. Falling back to internal knowledge.")
        return "Focus on general trends for January 2026."
    
    tavily = TavilyClient(api_key=tavily_key)
    # Search for real events happening TODAY in the USA
    query = f"Latest {niche} news headlines USA January 11 2026 trending"
    
    try:
        search_result = tavily.search(query=query, topic="news", days=1, max_results=5)
        context = "REAL-TIME CONTEXT FOR JAN 11, 2026:\n"
        for result in search_result['results']:
            context += f"- {result['title']}: {result['content']}\n"
        return context
    except Exception as e:
        logging.error(f"❌ Search Error: {e}")
        return "Focus on current 2026 industry standards."

def get_pexels_image(query):
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key: return None, None
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get('photos'):
                photo_url = data['photos'][0]['src']['large']
                img_res = requests.get(photo_url, timeout=10)
                return img_res.content, "image/jpeg"
    except Exception as e:
        logging.warning(f"⚠️ Image skip: {e}")
    return None, None

def clean_for_xml(text):
    if not text: return ""
    return "".join(c for c in text if c.isprintable()).encode('utf-8', 'ignore').decode('utf-8')

def publish():
    # --- 2. ENVIRONMENT CHECK ---
    groq_api_key = os.getenv("GROQ_API_KEY")
    wp_url = os.getenv("WP_URL")
    wp_user = os.getenv("WP_USER")
    wp_pass = os.getenv("WP_PASS")

    if not all([groq_api_key, wp_url, wp_user, wp_pass]):
        logging.error("❌ Missing Env Variables. Check your Secrets.")
        return

    NICHE_PROFILES = {
        "USA Politics": "draft",
        "Economics": "draft",
        "Sports": "publish",
        "Crypto": "publish",
        "Entertainment": "publish"
    }
    niche = random.choice(list(NICHE_PROFILES.keys()))
    
    # --- 3. FETCH LIVE DATA ---
    logging.info(f"🔎 Fact-checking {niche} for January 11, 2026...")
    live_facts = get_live_context(niche)
    
    # --- 4. THE SENIOR EDITOR PROMPT ---
    system_message = (
        "You are the Senior Editor for GCHAM News. "
        "You write data-dense, 800-word professional reports. "
        "USE THE PROVIDED LIVE CONTEXT to ensure 100% factual accuracy for Jan 11, 2026. "
        "Structure: <h1> Headline, <h2>/<h3> subheaders, <ul> lists. No emojis."
    )

    user_message = (
        f"CONTEXT: {live_facts}\n\n"
        f"TASK: Write a 800-word news report for the {niche} niche. "
        f"Ensure you mention specific names, events, and data points from the context. "
        f"Return ONLY a raw JSON object: "
        '{"headline": "", "body_html": "", "img_keyword": ""}'
    )

    client = Groq(api_key=groq_api_key)
    
    try:
        # Generation
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        data = json.loads(res.choices[0].message.content)

        # --- 5. WORDPRESS DEPLOYMENT ---
        wp = Client(wp_url, wp_user, wp_pass)
        
        img_bits, img_type = get_pexels_image(data.get('img_keyword', niche))
        f_id = None
        if img_bits:
            try:
                u_res = wp.call(media.UploadFile({
                    'name': f"g_{int(time.time())}.jpg", 
                    'type': img_type, 
                    'bits': xmlrpc_client.Binary(img_bits)
                }))
                f_id = u_res.get('id')
            except: logging.warning("⚠️ Image upload failed.")

        post = WordPressPost()
        post.title = clean_for_xml(data.get('headline', 'GCHAM News Update'))
        header_sig = f"<p>By <strong>Brayan Juma</strong> — Editor</p><hr>"
        post.content = header_sig + clean_for_xml(data.get('body_html', ''))
        post.post_status = NICHE_PROFILES[niche]
        if f_id: post.thumbnail = f_id

        wp.call(posts.NewPost(post))
        logging.info(f"✅ SUCCESS: {post.title} posted to {niche}")

    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR: {e}")

if __name__ == "__main__":
    publish()
