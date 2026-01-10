import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG & HEADERS ---
SYSTEM_VERSION = "GCHAM Authority v3.3 — The Master Build"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pexels_image(query):
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key: return None, None
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200 and res.json().get('photos'):
            photo_url = res.json()['photos'][0]['src']['large']
            img_res = requests.get(photo_url, timeout=12)
            return img_res.content, "image/jpeg"
    except Exception: return None, None

def enforce_ap_style(text, is_headline=False):
    if text is None or not isinstance(text, str): return ""
    # Expanded Protected Entities for 2026
    PROTECTED = {"U.S.", "NFL", "AI", "GOP", "SEC", "CEO", "GDP", "NASA", "BTC", "ETH", "CFTC", "GENIUS"}
    if is_headline:
        words = text.split()
        if not words: return ""
        headline = [words[0].title()]
        for w in words[1:]:
            clean_w = w.strip('.,!?:')
            headline.append(w if clean_w.upper() in PROTECTED else w.lower())
        text = ' '.join(headline)
        titles = ['coach', 'sen\\.', 'rep\\.', 'gov\\.', 'dr\\.', 'president', 'chairman']
        for t in titles: text = re.sub(f'\\b{t}\\b', t, text, flags=re.I)
        return text.replace('"', "'")
    return re.sub(r'\s+', ' ', text).strip()

def publish():
    # --- 2. THE EDITORIAL ANCHORS ---
    CURRENT_DATE = "Jan. 10, 2026"
    CONGRESS = "119th Congress"
    
    # We alternate between "Short News" and "Authority Deep Dives"
    is_deep_dive = random.choice([True, False])
    target_words = "800 words" if is_deep_dive else "500 words"
    
    NICHE_PROFILES = {
        "USA Politics": {"state": "WASHINGTON", "status": "draft", "search": "Capitol Hill"},
        "Economics": {"state": "NEW YORK", "status": "publish", "search": "Finance"},
        "Sports": {"state": "SANTA CLARA", "status": "publish", "search": "NFL stadium"},
        "Crypto": {"state": "MIAMI", "status": "publish", "search": "Bitcoin"}
    }
    niche = random.choice(list(NICHE_PROFILES.keys()))
    profile = NICHE_PROFILES[niche]

    # --- 3. THE "AUTHORITY" PROMPT ---
    # This prompt tells the AI EXACTLY why the Crypto article was better.
    gen_prompt = f"""
    JSON ONLY. Senior Editor at GCHAM. Today: {CURRENT_DATE}. 
    STYLE: Professional USA Blog (Inverted Pyramid).
    CONTEXT: {niche} in 2026 ({CONGRESS} session). 
    STRICT RULES: 
    1. NO mention of "COVID" or "Pandemic". Focus on 2026 debt, AI, and policy.
    2. USE DENSE DATA. Mention specific bills, committees, or athlete names.
    3. HIERARCHY: Use <h2> for main themes, <h3> for analysis, and <h4> for specific data/examples.
    
    STRUCTURE: {target_words}.
    JSON SCHEMA:
    {{
      "headline": "H1 Main Title",
      "summary": "2-sentence SEO italicized hook",
      "body_html": "Full structured body content starting with lede, using h2, h3, h4 tags.",
      "outlook": "Strategic 2026 outlook section text",
      "img_keyword": "2-word search for Pexels"
    }}
    """

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": gen_prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)

        # --- 4. DEPLOYMENT ---
        wp = Client(os.getenv("WP_URL"), os.getenv("WP_USER"), os.getenv("WP_PASS"))
        
        # Safe Image Handling
        img_bits, img_type = get_pexels_image(data.get('img_keyword', niche))
        f_id = None
        if img_bits:
            u_res = wp.call(media.UploadFile({
                'name': f"g_{int(time.time())}.jpg", 'type': img_type, 'bits': xmlrpc_client.Binary(img_bits)
            }))
            f_id = u_res.get('id')

        # Assembling with Authority Hierarchy
        post = WordPressPost()
        post.title = enforce_ap_style(data.get('headline'), True)
        post.content = f"""
        <p>By <strong>Brayan Juma</strong> — Editor</p>
        <p><em>{data.get('summary')}</em></p>
        <hr>
        {data.get('body_html')}
        <br>
        <h2>Strategic 2026 Outlook</h2>
        <p>{enforce_ap_style(data.get('outlook'))}</p>
        """
        
        post.post_status = profile['status']
        if f_id: post.thumbnail = f_id
        post.terms_names = {'category': [niche], 'post_tag': [niche, '2026', 'Deep Dive' if is_deep_dive else 'Update']}

        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ MISSION SUCCESS [{target_words}]: {post.title} (ID: {post_id})")

    except Exception as e:
        logging.error(f"❌ ERROR IN v3.3: {e}")

if __name__ == "__main__":
    publish()
