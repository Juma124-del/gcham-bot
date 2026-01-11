import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Empire Shield v5.1"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_live_context(niche):
    """Fetches real-time 2026 facts for the USA market"""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        return "General 2026 industry trends."
    
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
        return "Focus on current 2026 standards."

def get_pexels_image(query):
    """Fetches a single image from Pexels based on keyword"""
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
    except: return None, None
    return None, None

def clean_for_xml(text):
    if not text: return ""
    return "".join(c for c in text if c.isprintable()).encode('utf-8', 'ignore').decode('utf-8')

def publish():
    # --- 2. CREDENTIALS ---
    groq_api_key = os.getenv("GROQ_API_KEY")
    wp_url = os.getenv("WP_URL")
    wp_user = os.getenv("WP_USER")
    wp_pass = os.getenv("WP_PASS")

    if not all([groq_api_key, wp_url, wp_user, wp_pass]):
        logging.error("❌ Missing Env Variables.")
        return

    NICHE_PROFILES = {
        "USA Politics": "draft",
        "Economics": "draft",
        "Sports": "publish",
        "Crypto": "publish",
        "Entertainment": "publish"
    }
    niche = random.choice(list(NICHE_PROFILES.keys()))
    live_facts = get_live_context(niche)
    
    # --- 3. THE 1500-WORD MULTI-IMAGE PROMPT ---
    system_message = (
        "You are the Senior Editor for GCHAM News. You write 1,500-word investigative reports. "
        "STYLE: Use the INVERTED PYRAMID. First 40 words must contain the main news. "
        "WORD COUNT: You MUST expand on technical analysis, historical context, and future 2026 predictions to reach 1,500 words. "
        "STYLING: Use <h2>, <h3>, <ul>, and 3 italicized pull-quotes in <p><em><blockquote>...</blockquote></em></p>. "
        "IMAGE PLACEMENT: You MUST insert the exact text '[[IMAGE_PLACEHOLDER]]' twice in the body where images should go."
    )

    user_message = (
        f"CONTEXT: {live_facts}\n\n"
        f"TASK: Write a 1,500-word definitive news report on {niche} for Jan 12, 2026. "
        "Include a 5-question FAQ at the end with 3 outbound links to Reuters or Bloomberg. "
        "Return ONLY a raw JSON object: "
        '{"headline": "", "body_html": "", "img_kw_featured": "", "img_kw_body": ""}'
    )

    client = Groq(api_key=groq_api_key)
    
    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_message}],
            response_format={"type": "json_object"},
            temperature=0.6
        )
        data = json.loads(res.choices[0].message.content)
        wp = Client(wp_url, wp_user, wp_pass)
        
        # --- 4. IMAGE PROCESSING ---
        body_content = data.get('body_html', '')
        
        # Featured Image
        feat_bits, feat_type = get_pexels_image(data.get('img_kw_featured', niche))
        f_id = None
        if feat_bits:
            up_feat = wp.call(media.UploadFile({'name': 'feat.jpg', 'type': feat_type, 'bits': xmlrpc_client.Binary(feat_bits)}))
            f_id = up_feat.get('id')

        # Body Image
        body_bits, body_type = get_pexels_image(data.get('img_kw_body', niche))
        if body_bits:
            up_body = wp.call(media.UploadFile({'name': 'body.jpg', 'type': body_type, 'bits': xmlrpc_client.Binary(body_bits)}))
            body_img_url = up_body.get('url')
            img_html = f'<figure class="wp-block-image"><img src="{body_img_url}" alt="News Coverage"/></figure>'
            # Replace placeholders with the actual image
            body_content = body_content.replace('[[IMAGE_PLACEHOLDER]]', img_html, 1)

        # --- 5. POST ASSEMBLY ---
        post = WordPressPost()
        post.title = clean_for_xml(data.get('headline', 'GCHAM News Update'))
        
        # Excerpt Signature at the top as requested
        header_sig = f"<p>By <strong>Brayan Juma</strong> — Chief Editor, GCHAM News</p><hr>"
        post.content = header_sig + clean_for_xml(body_content)
        
        post.post_status = NICHE_PROFILES[niche]
        if f_id: post.thumbnail = f_id

        wp.call(posts.NewPost(post))
        logging.info(f"✅ SUCCESS: {post.title} posted with 2 images.")

    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR: {e}")

if __name__ == "__main__":
    publish()
