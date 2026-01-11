import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Empire Shield v5.0"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_live_context(niche):
    """Fetches real-time 2026 facts for the USA market"""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        logging.warning("⚠️ No TAVILY_API_KEY found.")
        return "General 2026 trends."
    
    tavily = TavilyClient(api_key=tavily_key)
    query = f"Latest breaking {niche} news headlines USA January 12 2026 trending"
    
    try:
        search_result = tavily.search(query=query, topic="news", days=1, max_results=5)
        context = "REAL-TIME CONTEXT FOR JAN 12, 2026:\n"
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
    groq_api_key = os.getenv("GROQ_API_KEY")
    wp_url = os.getenv("WP_URL")
    wp_user = os.getenv("WP_USER")
    wp_pass = os.getenv("WP_PASS")

    if not all([groq_api_key, wp_url, wp_user, wp_pass]):
        logging.error("❌ Missing Env Variables.")
        return

    # Rotation logic for 10 posts/day
    NICHE_PROFILES = {
        "USA Politics": "draft",
        "Economics": "draft",
        "Sports": "publish",
        "Crypto": "publish",
        "Entertainment": "publish"
    }
    niche = random.choice(list(NICHE_PROFILES.keys()))
    
    live_facts = get_live_context(niche)
    
    # --- THE EMPIRE BUILDER PROMPT ---
    system_message = (
        "You are the Senior Editor for GCHAM News. You write 1,500-word investigative reports. "
        "STYLE: Use the INVERTED PYRAMID. Lead with the most important facts (Who, What, Where, Why) in the first 40 words. "
        "STYLING: Use <h2>/<h3>, <ul>, and 3 italicized pull-quotes in <p><em><blockquote>...</blockquote></em></p> format. "
        "FAQ: Include a 5-question FAQ at the end with 3 outbound authority links to Reuters, Bloomberg, or Variety."
    )

    user_message = (
        f"CONTEXT: {live_facts}\n\n"
        f"TASK: Write a definitive 1,500-word news report for the {niche} niche for Jan 12, 2026. "
        "Ensure deep technical analysis and specific data points. "
        "Return ONLY a raw JSON object: "
        '{"headline": "", "body_html": "", "img_keyword": ""}'
    )

    client = Groq(api_key=groq_api_key)
    
    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.6
        )
        data = json.loads(res.choices[0].message.content)

        # --- WORDPRESS & SEO DEPLOYMENT ---
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
        
        # Adding Meta Robots and Author Signature
        seo_meta = "<meta name='robots' content='index, follow'><p><em>Jan 12, 2026</em></p>"
        header_sig = f"{seo_meta}<p>By <strong>Brayan Juma</strong> — Chief Editor, GCHAM News</p><hr>"
        
        post.content = header_sig + clean_for_xml(data.get('body_html', ''))
        post.post_status = NICHE_PROFILES[niche]
        if f_id: post.thumbnail = f_id

        wp.call(posts.NewPost(post))
        logging.info(f"✅ SUCCESS: {post.title} posted to {niche}")

    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR: {e}")

if __name__ == "__main__":
    publish()
