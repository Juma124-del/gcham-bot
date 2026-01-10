import os, json, re, random, logging, time
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts

# --- 1. VERSIONING ---
SYSTEM_VERSION = "GCHAM Production v2.2 — Jan 10, 2026 Build"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def truncate_headline(text, limit=80):
    if len(text) <= limit: return text
    return text[:limit].rsplit(' ', 1)[0]

def publish():
    # FAIL-FAST CHECK
    if not all([os.getenv("GROQ_API_KEY"), os.getenv("WP_URL")]):
        logging.error("❌ Missing critical Environment Variables.")
        return

    logging.info(f"🚀 {SYSTEM_VERSION}: BUILDING SUBSTANTIAL CONTENT")
    
    # --- 2. THE 2026 ANCHOR (Hard-coded Accuracy) ---
    CURRENT_YEAR = "2026"
    CONGRESS = "119th Congress"
    ELECTION_CYCLE = "2026 Midterm Elections"

    EDITORIAL_CONTEXT = {
        "sports": {"season": "2025–26 NFL postseason", "week": "Wild Card Round"},
        "politics": {"focus": f"{CONGRESS} second session and {ELECTION_CYCLE} strategy"},
        "economics": {"focus": "Q1 2026 Inflation and Market Volatility"}
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

    # --- 3. REFINED STYLE ENGINE ---
    def enforce_mode_constraints(mode, text):
        if mode == "evergreen":
            banned = ["today", "yesterday", "this week", "last night", "tonight", "recently", "now", "currently", "at present"]
            for b in banned:
                text = re.sub(rf"\b{b}\b", "", text, flags=re.I)
        return re.sub(r'\s+', ' ', text).strip()

    def enforce_universal_ap_style(text, niche, is_headline=False):
        if is_headline:
            # Acronym Protection + Proper AP Case
            PROTECTED = {"U.S.", "NFL", "AI", "NBA", "FCC", "SEC", "CEO", "GDP", "GOP"}
            words = text.split()
            if words:
                headline = [words[0].title()]
                for w in words[1:]:
                    clean_w = w.strip('.,!?:')
                    headline.append(w if clean_w.upper() in PROTECTED else w.lower())
                text = ' '.join(headline)
            
            # Expanded Title Protection
            titles = ['coach', 'sen\\.', 'rep\\.', 'gov\\.', 'dr\\.', 'ceo', 'president', 'justice']
            for title in titles:
                text = re.sub(f'\\b{title}\\b', title, text, flags=re.I)
            return text.replace('"', "'")

        text = re.sub(r'\b(Mr\.|Mrs\.|Ms\.)\s', '', text)
        return text.strip()

    # --- 4. THE "SUBSTANCE" PROMPT (Fixes Length) ---
    ctx = EDITORIAL_CONTEXT.get(niche.lower(), {"focus": "General Trends"})
    
    # NEW: Specific instructions for 3-part structure and 500+ words
    gen_prompt = f"""
    SYSTEM: You are a senior AP journalist in {CURRENT_YEAR}. 
    CONTEXT: {ctx}. 
    TASK: Write a 500-word {niche} article on a major {CURRENT_YEAR} development. 
    REQUIRED STRUCTURE:
    1. Lede (30 words max, CITY — dateline format)
    2. Analysis (2-3 paragraphs of background and current data)
    3. Outlook (Future implications for the rest of {CURRENT_YEAR})
    JSON ONLY: {{'headline': '', 'lede': '', 'body': ''}}
    """
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    data = None
    for attempt in range(3):
        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile", 
                messages=[{"role": "user", "content": gen_prompt}], 
                response_format={"type": "json_object"}, 
                timeout=45 # Increased timeout for longer content
            )
            raw_content = res.choices[0].message.content
            clean_json = re.sub(r"```json|```", "", raw_content).strip()
            data = json.loads(clean_json)
            break
        except Exception as e:
            logging.warning(f"⚠️ Attempt {attempt+1}/3 failed: {e}")
            time.sleep(2)
    
    if not data: return

    # --- 5. FINAL ASSEMBLY ---
    try:
        headline = truncate_headline(enforce_universal_ap_style(data['headline'], niche, True))
        lede = enforce_mode_constraints(mode, enforce_universal_ap_style(data['lede'], niche))
        body = enforce_mode_constraints(mode, enforce_universal_ap_style(data['body'], niche))

        wp = Client(os.getenv("WP_URL"), os.getenv("WP_USER"), os.getenv("WP_PASS"))
        post = WordPressPost()
        post.title = headline
        # Standardized layout for better readability
        post.content = f"<p>By <strong>Brayan Juma</strong> — Editor</p>{profile['state']} — {lede}\n\n{body}"
        post.post_status = profile['status']
        post.custom_fields = [{"key": "system_version", "value": SYSTEM_VERSION}]

        wp.call(posts.NewPost(post))
        logging.info(f"✅ v2.2 DEPLOYED: {headline} (Enhanced Length)")

    except Exception as e:
        logging.error(f"❌ v2.2 FAILED: {e}")

if __name__ == "__main__":
    publish()
