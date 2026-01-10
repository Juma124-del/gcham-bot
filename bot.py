import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Authority v3.2 — Long-Form Build"
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY") 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pexels_image(query):
    if not PEXELS_API_KEY: return None, None
    headers = {"Authorization": PEXELS_API_KEY}
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
    # --- 2. THE DYNAMIC LENGTH LOGIC ---
    # Randomly choose between a 'Quick Update' (~400 words) and a 'Deep Dive' (~800 words)
    article_type = random.choice(["Quick Update", "Deep Dive"])
    word_count = "400" if article_type == "Quick Update" else "800"
    
    CURRENT_DATE = "Jan. 10, 2026"
    NICHE_PROFILES = {
        "USA Politics": {"state": "WASHINGTON", "status": "draft", "search": "Capitol Hill"},
        "Economics": {"state": "NEW YORK", "status": "publish", "search": "Finance"},
        "Sports": {"state": "SANTA CLARA", "status": "publish", "search": "NFL"},
        "Crypto": {"state": "MIAMI", "status": "publish", "search": "Crypto"}
    }
    niche = random.choice(list(NICHE_PROFILES.keys()))
    profile = NICHE_PROFILES[niche]

    # --- 3. THE "H-TAG HIERARCHY" PROMPT ---
    gen_prompt = f"""
    JSON ONLY. Senior Editor at GCHAM. Today: {CURRENT_DATE}. 
    STRICT: No mention of Pandemic/COVID. 
    TASK: Write a {article_type} ({word_count} words) on {niche}.
    
    REQUIRED HTML STRUCTURE IN 'body' field:
    - Start with the Lede.
    - Use <h2> for major sections.
    - Use <h3> for detailed analysis.
    - Use <h4> for specific examples or data points.
    
    JSON STRUCTURE:
    {{"headline": "H1 title", "summary": "Italic SEO summary", "body": "Full HTML content with h2, h3, h4", "outlook": "Final section", "img_keyword": ""}}
    """

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": gen_prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)

        # --- 4. IMAGE & WP DEPLOY ---
        wp = Client(os.getenv("WP_URL"), os.getenv("WP_USER"), os.getenv("WP_PASS"))
        img_result = get_pexels_image(data.get('img_keyword', niche))
        img_bits, img_type = img_result if img_result else (None, None)
        f_id = None
        if img_bits:
            u_res = wp.call(media.UploadFile({'name': f"g_{int(time.time())}.jpg", 'type': img_type, 'bits': xmlrpc_client.Binary(img_bits)}))
            f_id = u_res.get('id')

        post = WordPressPost()
        post.title = enforce_ap_style(data.get('headline'), True)
        
        # Assembling the Authoritative Blog Post
        post.content = f"""
        <p>By <strong>Brayan Juma</strong> — Editor</p>
        <p><em>{data.get('summary')}</em></p>
        <hr>
        {data.get('body')}
        <br>
        <h2>Strategic 2026 Outlook</h2>
        <p>{data.get('outlook')}</p>
        """
        
        post.post_status = profile['status']
        if f_id: post.thumbnail = f_id
        post.terms_names = {'category': [niche], 'post_tag': [niche, '2026', article_type]}

        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ DEPLOYED {article_type}: {post.title} [ID: {post_id}]")

    except Exception as e:
        logging.error(f"❌ FAILED: {e}")

if __name__ == "__main__":
    publish()
