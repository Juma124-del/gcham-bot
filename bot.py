import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Executive v2.9 — Type-Safe Build"
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY") 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pexels_image(query):
    if not PEXELS_API_KEY: return None, None
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200 and res.json()['photos']:
            photo_url = res.json()['photos'][0]['src']['large']
            img_res = requests.get(photo_url, timeout=12)
            return img_res.content, "image/jpeg"
    except Exception: return None, None

def enforce_ap_style(text, is_headline=False):
    """UPDATED: Type-Safe AP Engine to prevent 'expected string' errors."""
    # FIX: Ensure 'text' is always a string. If it's None or a list, convert it.
    if text is None: return ""
    if not isinstance(text, str): 
        text = str(text) # Force conversion to string
    
    PROTECTED = {"U.S.", "NFL", "AI", "GOP", "SEC", "CEO", "GDP", "NASA", "CES", "BTC", "ETH"}
    
    if is_headline:
        words = text.split()
        if not words: return ""
        headline = [words[0].title()]
        for w in words[1:]:
            clean_w = w.strip('.,!?:')
            headline.append(w if clean_w.upper() in PROTECTED else w.lower())
        text = ' '.join(headline)
        titles = ['coach', 'sen\\.', 'rep\\.', 'gov\\.', 'dr\\.', 'president', 'justice']
        for t in titles: text = re.sub(f'\\b{t}\\b', t, text, flags=re.I)
        return text.replace('"', "'")
    
    return re.sub(r'\s+', ' ', text).strip()

def publish():
    # Credentials check
    groq_key = os.getenv("GROQ_API_KEY")
    wp_url = os.getenv("WP_URL")
    if not groq_key or not wp_url:
        logging.error("❌ CRITICAL: Credentials missing.")
        return

    CURRENT_DATE = "Jan. 10, 2026"
    NICHE_PROFILES = {
        "USA Politics": {"state": "WASHINGTON", "status": "draft", "search": "US Capitol"},
        "Economics": {"state": "NEW YORK", "status": "publish", "search": "Wall Street"},
        "Sports": {"state": "SANTA CLARA", "status": "publish", "search": "NFL"},
        "Crypto": {"state": "MIAMI", "status": "publish", "search": "Bitcoin"}
    }

    niche = random.choice(list(NICHE_PROFILES.keys()))
    profile = NICHE_PROFILES[niche]

    gen_prompt = f"OUTPUT VALID JSON ONLY. Today is {CURRENT_DATE}. Write a 500-word news report on {niche} in 2026 for GCHAM News. Use keys: headline, summary, lede, body, outlook, img_keyword."

    client = Groq(api_key=groq_key)
    
    data = None
    for attempt in range(3):
        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": gen_prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)
            break
        except Exception as e:
            logging.warning(f"⚠️ Retry {attempt+1}: {e}")
            time.sleep(2)

    if not data: return

    try:
        wp = Client(wp_url, os.getenv("WP_USER"), os.getenv("WP_PASS"))
        
        # Image logic
        img_bits, img_type = get_pexels_image(data.get('img_keyword', 'news'))
        f_id = None
        if img_bits:
            u_res = wp.call(media.UploadFile({'name': f"g_{int(time.time())}.jpg", 'type': img_type, 'bits': xmlrpc_client.Binary(img_bits)}))
            f_id = u_res['id']

        post = WordPressPost()
        # Using .get() to avoid KeyErrors
        post.title = enforce_ap_style(data.get('headline', 'GCHAM News Update'), True)
        post.content = f"""
        <p>By <strong>Brayan Juma</strong> — Editor</p>
        <p><em>{data.get('summary', '')}</em></p>
        <hr>
        <p><strong>{enforce_ap_style(data.get('lede', ''))}</strong></p>
        {enforce_ap_style(data.get('body', ''))}
        <br>
        <h3>Strategic 2026 Outlook</h3>
        <p>{enforce_ap_style(data.get('outlook', ''))}</p>
        """
        post.post_status = profile['status']
        post.thumbnail = f_id
        post.terms_names = {'category': [niche], 'post_tag': [niche, '2026']}

        wp.call(posts.NewPost(post))
        logging.info(f"✅ MISSION SUCCESS: {post.title}")

    except Exception as e:
        logging.error(f"❌ DEPLOYMENT FAILED: {e}")

if __name__ == "__main__":
    publish()
