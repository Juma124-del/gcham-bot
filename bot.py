import os, json, re, random, requests, logging, time, socket
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Empire Shield v5.3"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 🛡️ GLOBAL TIMEOUT SETTING (Protects the entire script from hanging)
socket.setdefaulttimeout(300) 

def get_live_context(niche):
    """Fetches real-time 2026 facts for the USA market with timeout"""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key: return "General 2026 industry trends."
    
    tavily = TavilyClient(api_key=tavily_key)
    query = f"Latest breaking {niche} news headlines USA January 2026 investigative"
    
    try:
        # 🛡️ Added timeout for search
        search_result = tavily.search(query=query, topic="news", days=3, max_results=5)
        context = "REAL-TIME CONTEXT FOR JANUARY 2026:\n"
        for result in search_result['results']:
            context += f"- {result['title']}: {result['content']}\n"
        return context
    except Exception as e:
        logging.error(f"❌ Search Error: {e}")
        return "Focus on current 2026 technical standards."

def get_pexels_image(query):
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key: return None, None
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    try:
        # 🛡️ Tight 15s timeout for image fetching
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data.get('photos'):
                photo_url = data['photos'][0]['src']['large']
                img_res = requests.get(photo_url, timeout=15)
                return img_res.content, "image/jpeg"
    except: return None, None
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
        logging.error("❌ Missing Env Variables.")
        return

    NICHE_PROFILES = {
        "USA Politics": "draft", "Economics": "draft",
        "Sports": "publish", "Crypto": "publish", "Entertainment": "publish"
    }
    niche = random.choice(list(NICHE_PROFILES.keys()))
    live_facts = get_live_context(niche)
    
    # --- 3. PROMPT STRATEGY (Inverted Pyramid + 1,500 Words) ---
    system_message = (
        "You are the Senior Editor for GCHAM News. You MUST write at least 1,500 words. "
        "STRUCTURE: Use the INVERTED PYRAMID (Lead news in first 40 words). "
        "EXPANSION LOGIC: To reach the word count, you MUST include these sections:\n"
        "1. SECTOR IMPACT: Separate H3 sections for Agriculture, Technology, and Manufacturing impact.\n"
        "2. HISTORICAL CONTEXT: Compare these 2026 events to relevant data from 2020-2025.\n"
        "3. GEOPOLITICAL IMPLICATIONS: How this affects USA relations with the world.\n"
        "4. CONSUMER OUTLOOK: Practical advice for the American citizen.\n"
        "PLACEHOLDERS: Insert '[[IMAGE_PLACEHOLDER]]' twice in the body text."
    )

    user_message = (
        f"CONTEXT: {live_facts}\n\n"
        f"TASK: Write a 1,500-word investigative report on {niche} for Jan 12, 2026. "
        "Include a 5-question FAQ with links to Reuters/Bloomberg at the end. "
        "Return ONLY a raw JSON object: "
        '{"headline": "", "body_html": "", "img_kw_featured": "", "img_kw_body": ""}'
    )

    # 🛡️ 180s Groq timeout to allow for massive generation
    client = Groq(api_key=groq_api_key, timeout=180.0)
    
    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_message}],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        data = json.loads(res.choices[0].message.content)
        wp = Client(wp_url, wp_user, wp_pass)
        
        # --- 4. MULTI-IMAGE INJECTION ---
        body_content = data.get('body_html', '')
        
        # Featured Image
        feat_bits, feat_type = get_pexels_image(data.get('img_kw_featured', niche))
        f_id = None
        if feat_bits:
            up_feat = wp.call(media.UploadFile({'name': 'feat.jpg', 'type': feat_type, 'bits': xmlrpc_client.Binary(feat_bits)}))
            f_id = up_feat.get('id')

        # Body Image
        body_bits, body_type = get_pexels_image(data.get('img_kw_body', f"{niche} industry"))
        if body_bits:
            up_body = wp.call(media.UploadFile({'name': 'body.jpg', 'type': body_type, 'bits': xmlrpc_client.Binary(body_bits)}))
            img_tag = f'<figure class="wp-block-image"><img src="{up_body.get("url")}" alt="2026 Report"/></figure>'
            body_content = body_content.replace('[[IMAGE_PLACEHOLDER]]', img_tag, 1)

        # --- 5. POST ASSEMBLY & INDEXING ---
        post = WordPressPost()
        post.title = clean_for_xml(data.get('headline', 'GCHAM News Daily'))
        
        # 🛡️ INDEXING TAGS: Tells Google to crawl and index immediately
        # We also keep your Author Header signature
        header_sig = (
            "<meta name='robots' content='index, follow, max-image-preview:large'>\n"
            f"<p>By <strong>Brayan Juma</strong> — Chief Editor, GCHAM News</p><hr>"
        )
        
        post.content = header_sig + clean_for_xml(body_content)
        post.post_status = NICHE_PROFILES[niche]
        
        # SEO: Add meta-description if possible via custom fields (Optional based on theme)
        post.custom_fields = [{'key': 'description', 'value': data.get('headline')[:160]}]
        
        if f_id: post.thumbnail = f_id

        # 🛡️ WordPress Retry Logic (Try 3 times if server is slow)
        for attempt in range(3):
            try:
                wp.call(posts.NewPost(post))
                logging.info(f"✅ SUCCESS: {post.title} published on attempt {attempt+1}.")
                break
            except Exception as wp_err:
                if attempt == 2: raise wp_err
                time.sleep(10)

    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR: {e}")

if __name__ == "__main__":
    publish()
