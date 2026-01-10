import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG & CREDENTIALS ---
SYSTEM_VERSION = "GCHAM Executive v2.7 — Final 2026 Build"
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY") 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pexels_image(query):
    """Automated Image Engine: Fetches high-res news imagery."""
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
    """Elite AP Style Engine: Handles acronyms and title protection."""
    if not text: return ""
    PROTECTED = {"U.S.", "NFL", "AI", "GOP", "SEC", "CEO", "GDP", "NASA", "CES"}
    if is_headline:
        words = text.split()
        headline = [words[0].title()]
        for w in words[1:]:
            clean_w = w.strip('.,!?:')
            headline.append(w if clean_w.upper() in PROTECTED else w.lower())
        text = ' '.join(headline)
        # Professional Title Protection (Sentence Case rules)
        titles = ['coach', 'sen\\.', 'rep\\.', 'gov\\.', 'dr\\.', 'president', 'justice']
        for t in titles: text = re.sub(f'\\b{t}\\b', t, text, flags=re.I)
        return text.replace('"', "'")
    return re.sub(r'\s+', ' ', text).strip()

def publish():
    # --- 2. THE 2026 CONTEXT SHIELD ---
    CURRENT_DATE = "Jan. 10, 2026"
    CONGRESS = "119th Congress"
    
    NICHE_PROFILES = {
        "USA Politics": {"state": "WASHINGTON", "status": "draft", "search": "US Capitol"},
        "Economics": {"state": "NEW YORK", "status": "publish", "search": "Stock Exchange"},
        "Sports": {"state": "SANTA CLARA", "status": "publish", "search": "NFL Action"},
        "Crypto": {"state": "MIAMI", "status": "publish", "search": "Digital Currency"}
    }

    niche = random.choice(list(NICHE_PROFILES.keys()))
    profile = NICHE_PROFILES[niche]

    # --- 3. THE "CITATION-READY" PROMPT ---
    gen_prompt = f"""
    SYSTEM: Senior News Editor at GCHAM. TODAY IS {CURRENT_DATE}. 
    STYLE: Inverted Pyramid. Focus on E-E-A-T (Experience, Expertise, Authoritativeness, Trust).
    CONTEXT: {niche} news for the {CONGRESS}. 
    JSON STRUCTURE:
    - "headline": Sentence case AP headline.
    - "summary": 2-sentence SEO hook in italics for AI crawlers.
    - "lede": {profile['state']} — Core news paragraph (50 words).
    - "body": 3-4 paragraphs of context, history, and data.
    - "outlook": Professional forecast for Q1 2026.
    - "img_keyword": 2-word photo search term.
    """

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # Retry Loop for Resilience
    data = None
    for attempt in range(3):
        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": gen_prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(re.sub(r"```json|```", "", res.choices[0].message.content).strip())
            break
        except Exception: time.sleep(2)

    if not data: return

    # --- 4. THE ASSEMBLY ---
    try:
        wp = Client(os.getenv("WP_URL"), os.getenv("WP_USER"), os.getenv("WP_PASS"))
        
        # Image Processing
        img_bits, img_type = get_pexels_image(data['img_keyword'])
        f_id = None
        if img_bits:
            u_res = wp.call(media.UploadFile({'name': f"g_{int(time.time())}.jpg", 'type': img_type, 'bits': xmlrpc_client.Binary(img_bits)}))
            f_id = u_res['id']

        # Final Scannable Layout
        post = WordPressPost()
        post.title = enforce_ap_style(data['headline'], True)
        post.content = f"""
        <p>By <strong>Brayan Juma</strong> — Editor</p>
        <p><em>{data['summary']}</em></p>
        <hr>
        <p><strong>{enforce_ap_style(data['lede'])}</strong></p>
        {enforce_ap_style(data['body'])}
        <br>
        <h3>Strategic 2026 Outlook</h3>
        <p>{enforce_ap_style(data['outlook'])}</p>
        """
        post.post_status = profile['status']
        post.thumbnail = f_id
        post.terms_names = {'category': [niche], 'post_tag': [data['img_keyword'], '2026']}

        wp.call(posts.NewPost(post))
        logging.info(f"✅ FINAL DEPLOYMENT SUCCESS: {post.title}")

    except Exception as e: logging.error(f"❌ DEPLOYMENT FAILED: {e}")

if __name__ == "__main__":
    publish()
