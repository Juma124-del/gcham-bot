import os, json, re, random, logging, time
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts

# --- 1. VERSIONING & SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Production v2.1 — Jan 2026"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def truncate_headline(text, limit=80):
    """Fix #2: Word-safe truncation to prevent cut-off words."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0]

def publish():
    # --- 2. FAIL-FAST ENVIRONMENT CHECK (Fix #3) ---
    required_vars = ["GROQ_API_KEY", "WP_URL", "WP_USER", "WP_PASS"]
    if not all(os.getenv(var) for var in required_vars):
        logging.error(f"❌ CRITICAL: Missing environment variables {required_vars}. Aborting.")
        return

    if os.getenv("FREEZE_PUBLISHING") == "true":
        logging.warning("🚫 EMERGENCY STOP: Publishing frozen.")
        return

    logging.info(f"🚀 {SYSTEM_VERSION}: STARTING MISSION")
    
    # --- 3. EDITORIAL CONFIG ---
    EDITORIAL_CONTEXT = {
        "sports": {"season": "2025–26 NFL postseason", "week": "Wild Card Round"},
        "politics": {"focus": "2026 Midterm Election cycle start"},
        "economics": {"focus": "Q1 2026 Inflation Reports"}
    }

    NICHE_PROFILES = {
        "USA Politics": {"state": "WASHINGTON, D.C.", "status": "draft", "mode": "news"},
        "Economics": {"state": "NEW YORK, N.Y.", "status": "publish", "mode": "evergreen"},
        "Tech News": {"state": "SAN FRANCISCO, Calif.", "status": "publish", "mode": "evergreen"},
        "Sports": {"state": "SANTA CLARA, Calif.", "status": "publish", "mode": "news"},
        "Entertainment": {"state": "LOS ANGELES, Calif.", "status": "publish", "mode": "news"}
    }

    niche = random.choice(list(NICHE_PROFILES.keys()))
    profile = NICHE_PROFILES[niche]
    mode = profile["mode"]

    # --- 4. CLEANING & STYLE ENGINES ---

    def enforce_mode_constraints(mode, text):
        """Fix #1: Removes time-anchors and collapses double spaces."""
        if mode == "evergreen":
            banned = ["today", "yesterday", "this week", "last night", "tonight", "recently", "now", "currently", "at present"]
            for b in banned:
                text = re.sub(rf"\b{b}\b", "", text, flags=re.I)
        
        # Collapse multiple spaces into one and strip
        return re.sub(r'\s+', ' ', text).strip()

    def enforce_universal_ap_style(text, niche, is_headline=False):
        if is_headline:
            PROTECTED = {"U.S.", "NFL", "AI", "NBA", "FCC", "SEC", "CEO", "GDP"}
            words = text.split()
            if words:
                headline = [words[0].title()]
                for w in words[1:]:
                    clean_w = w.strip('.,!?:')
                    headline.append(w if clean_w.upper() in PROTECTED else w.lower())
                text = ' '.join(headline)
            
            # Lowercase job titles / Standardize AP
            titles = ['coach', 'sen\\.', 'rep\\.', 'gov\\.', 'dr\\.', 'ceo']
            for title in titles:
                text = re.sub(f'\\b{title}\\b', title, text, flags=re.I)
            return text.replace('"', "'")

        text = re.sub(r'\b(Mr\.|Mrs\.|Ms\.)\s', '', text)
        return text.strip()

    # --- 5. RESILIENT GENERATION (Retry Logic + JSON Fix) ---
    ctx = EDITORIAL_CONTEXT.get(niche.lower(), {"focus": "General Trends"})
    gen_prompt = f"Date: Jan 10, 2026. Mode: {mode.upper()}. Context: {ctx}. Write {niche} article. JSON ONLY: {{'headline': '', 'lede': '', 'body': ''}}"
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # Retry Loop (Fix #5)
    data = None
    for attempt in range(3):
        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile", 
                messages=[{"role": "user", "content": gen_prompt}], 
                response_format={"type": "json_object"}, 
                timeout=30
            )
            # JSON Sanitization (Fix #4)
            raw_content = res.choices[0].message.content
            clean_json = re.sub(r"```json|```", "", raw_content).strip()
            data = json.loads(clean_json)
            break
        except Exception as e:
            logging.warning(f"⚠️ Attempt {attempt+1}/3 failed: {e}")
            time.sleep(2) # Brief pause before retry
    
    if not data:
        logging.error("❌ All generation attempts failed. Aborting.")
        return

    # --- 6. FINAL ASSEMBLY & DEPLOY ---
    try:
        # Style -> Mode Constraints -> Truncate
        headline = truncate_headline(enforce_universal_ap_style(data['headline'], niche, True))
        lede = enforce_mode_constraints(mode, enforce_universal_ap_style(data['lede'], niche))
        body = enforce_mode_constraints(mode, enforce_universal_ap_style(data['body'], niche))

        wp = Client(os.getenv("WP_URL"), os.getenv("WP_USER"), os.getenv("WP_PASS"))
        post = WordPressPost()
        post.title = headline
        post.content = f"<p>By <strong>Brayan Juma</strong> — Editor</p>{profile['state']} — {lede}\n\n{body}"
        post.post_status = profile['status']
        post.custom_fields = [{"key": "system_version", "value": SYSTEM_VERSION}]

        wp.call(posts.NewPost(post))
        logging.info(f"✅ v2.1 MISSION SUCCESS: {headline}")

    except Exception as e:
        logging.error(f"❌ v2.1 DEPLOYMENT FAILED: {e}")

if __name__ == "__main__":
    publish()
