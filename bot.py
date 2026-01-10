import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Production v3.0 — Unstoppable"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pexels_image(query):
    """FIXED: Safe image fetching that never returns a 'None' that crashes the script."""
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key: return None, None
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200 and res.json().get('photos'):
            photo_url = res.json()['photos'][0]['src']['large']
            img_res = requests.get(photo_url, timeout=10)
            return img_res.content, "image/jpeg"
    except Exception as e:
        logging.warning(f"🖼️ Image error (Safe skip): {e}")
    return None, None # This is now handled safely in publish()

def enforce_ap_style(text, is_headline=False):
    """Our Elite Style Engine (Preserved from v2.7)."""
    if not text or not isinstance(text, str): return ""
    PROTECTED = {"U.S.", "NFL", "AI", "GOP", "SEC", "CEO", "GDP", "NASA", "BTC", "ETH"}
    if is_headline:
        words = text.split()
        if not words: return ""
        headline = [words[0].title()]
        for w in words[1:]:
            clean_w = w.strip('.,!?:')
            headline.append(w if clean_w.upper() in PROTECTED else w.lower())
        text = ' '.join(headline)
        titles = ['coach', 'sen\\.', 'rep\\.', 'gov\\.', 'dr\\.', 'president']
        for t in titles: text = re.sub(f'\\b{t}\\b', t, text, flags=re.I)
        return text.replace('"', "'")
    return re.sub(r'\s+', ' ', text).strip()

def publish():
    # --- 2. CREDENTIALS & NICHE ---
    REQUIRED = ["GROQ_API_KEY", "WP_URL", "WP_USER", "WP_PASS"]
    if not all(os.getenv(k) for k in REQUIRED):
        logging.error("❌ Missing Environment Variables.")
        return

    NICHE_PROFILES = {
        "USA Politics": {"state": "WASHINGTON", "status": "draft", "search": "US Capitol"},
        "Economics": {"state": "NEW YORK", "status": "publish", "search": "Wall Street"},
        "Sports": {"state": "SANTA CLARA", "status": "publish", "search": "NFL stadium"},
        "Crypto": {"state": "MIAMI", "status": "publish", "search": "Bitcoin"}
    }
    niche = random.choice(list(NICHE_PROFILES.keys()))
    profile = NICHE_PROFILES[niche]

    # --- 3. BULLETPROOF GENERATION ---
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    gen_prompt = f"Date: Jan 10, 2026. Write 500-word {niche} news. JSON ONLY: {{'headline': '', 'summary': '', 'lede': '', 'body': '', 'outlook': '', 'img_keyword': ''}}"

    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": gen_prompt}],
            response_format={"type": "json_object"}
        )
        
        # Safe JSON Parsing
        raw_text = res.choices[0].message.content.strip()
        data = json.loads(raw_text)
        
        # --- 4. SAFE IMAGE UNPACKING (The Crash Fix) ---
        img_result = get_pexels_image(data.get('img_keyword', niche))
        img_bits, img_type = img_result if img_result else (None, None)
        
        f_id = None
        wp = Client(os.getenv("WP_URL"), os.getenv("WP_USER"), os.getenv("WP_PASS"))

        if img_bits:
            try:
                u_res = wp.call(media.UploadFile({
                    'name': f"gcham_{int(time.time())}.jpg",
                    'type': img_type,
                    'bits': xmlrpc_client.Binary(img_bits)
                }))
                f_id = u_res.get('id')
            except Exception as e:
                logging.warning(f"🖼️ Media upload failed: {e}")

        # --- 5. FINAL DEPLOYMENT ---
        post = WordPressPost()
        post.title = enforce_ap_style(data.get('headline', 'GCHAM Update'), True)
        post.content = f"""
        <p>By <strong>Brayan Juma</strong> — Editor</p>
        <p><em>{enforce_ap_style(data.get('summary', ''))}</em></p>
        <hr>
        <p><strong>{enforce_ap_style(data.get('lede', ''))}</strong></p>
        {enforce_ap_style(data.get('body', ''))}
        <br>
        <h3>Strategic 2026 Outlook</h3>
        <p>{enforce_ap_style(data.get('outlook', ''))}</p>
        """
        post.post_status = profile['status']
        if f_id: post.thumbnail = f_id
        post.terms_names = {'category': [niche], 'post_tag': ['2026', niche]}

        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ LIVE: {post.title} [ID: {post_id}]")

    except Exception as e:
        logging.error(f"❌ SYSTEM FAILURE: {e}")

if __name__ == "__main__":
    publish()
