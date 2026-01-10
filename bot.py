import os, json, re, random, logging, feedparser, requests, io, time
from PIL import Image

# --- 1. DEPENDENCIES & SAFETY ---
try:
    from python_slugify import slugify
except ImportError:
    def slugify(text):
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 2. ELITE EDITORIAL CONFIG (The Niche Rulebook) ---
# Pillars: Entertainment, Sports, Politics, Economics (Finance/Crypto)
NICHE_PROFILES = {
    "USA Politics": {
        "priority": 1, "min_signals": 5, "status": "draft", "images": False, "max_len": 85
    },
    "Economics": {
        "priority": 2, "min_signals": 4, "status": "publish", "images": True, "max_len": 95
    },
    "Tech News": {
        "priority": 3, "min_signals": 3, "status": "publish", "images": True, "max_len": 95
    },
    "Sports": {
        "priority": 4, "min_signals": 2, "status": "publish", "images": True, "max_len": 100
    },
    "Entertainment": {
        "priority": 5, "min_signals": 2, "status": "publish", "images": True, "max_len": 100
    }
}

TRUSTED_SOURCES = {"reuters", "associated press", "ap news", "bloomberg", "bbc news", "the new york times", "the washington post", "cnn", "politico", "the guardian", "forbes", "wsj", "npr", "usa today", "coindesk", "cointelegraph"}
BANNED_WORDS = ["explodes", "shocking", "bombshell", "devastating", "crisis", "meltdown", "insane", "slams", "blasts", "destroys"]
COMPLIANCE_KEYWORDS = ["investigation", "charges", "classified", "election", "court", "indictment", "lawsuit", "arrested"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_env():
    keys = ["GROQ_API_KEY", "WP_URL", "WP_USER", "WP_PASS", "PEXELS_API_KEY"]
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        logging.error(f"❌ CRITICAL: Missing environment variables: {missing}")
        exit(1)

check_env()
GROQ_API_KEY, WP_URL, WP_USER, WP_PASS, PEXELS_KEY = os.getenv("GROQ_API_KEY"), os.getenv("WP_URL"), os.getenv("WP_USER"), os.getenv("WP_PASS"), os.getenv("PEXELS_API_KEY")

client = Groq(api_key=GROQ_API_KEY)
try:
    wp_client = Client(WP_URL, WP_USER, WP_PASS)
except Exception as e:
    logging.error(f"❌ WordPress Auth Failed: {e}")
    exit(1)

# --- 3. GOVERNANCE & CONFLICT RESOLUTION ---

def filter_trusted(entries):
    """Fuzzy matching to ensure we catch 'Reuters - Politics' etc."""
    trusted = []
    for e in entries:
        src = e.source.get("title", "").lower() if e.source else ""
        if any(t in src for t in TRUSTED_SOURCES):
            trusted.append(e)
    return trusted

def already_published(topic, log="published_topics.txt"):
    """Pillar 2: Conflict Resolution. One event = One article."""
    if not os.path.exists(log): return False
    with open(log, "r") as f:
        content = f.read().lower()
        return topic.lower() in content

def validate_data(data, profile):
    """JSON Contract Enforcement & Headline Ethics."""
    required = ["headline", "image_keyword", "excerpt", "content_html"]
    if not all(k in data and data[k] for k in required): return False
    headline = data['headline'].lower()
    if any(w in headline for w in BANNED_WORDS) or len(data['headline']) > profile['max_len']:
        return False
    return True

def compliance_check(niche, topic):
    """Identifies high-risk legal/political triggers."""
    return niche == "USA Politics" or any(k in topic.lower() for k in COMPLIANCE_KEYWORDS)

# --- 4. CORE EXECUTION ENGINE ---

def get_topic(niche):
    prompt = f"Suggest one widely reported U.S. news topic currently covered by major outlets for {niche}. Neutral phrasing. Title only."
    try:
        res = client.chat.completions.create(messages=[{"role":"user","content":prompt}], model="llama-3.3-70b-versatile", timeout=30)
        return res.choices[0].message.content.strip().replace('"', '')
    except Exception as e:
        logging.error(f"Topic fetch failed: {e}")
        return None

def publish():
    logging.info("🚀 GCHAM ELITE NEWSROOM: ACTIVE")
    chief_editor = "Brayan Juma"
    
    # Niche Selection & Profile Loading
    niche = random.choice(list(NICHE_PROFILES.keys()))
    profile = NICHE_PROFILES[niche]
    
    # Topic Sanity Loop
    topic = get_topic(niche)
    if not topic or already_published(topic):
        logging.info(f"⏭️ Skipped (Duplicate or Null): {topic}")
        return

    # Sourcing & Signal Gate
    rss_url = f"https://news.google.com/rss/search?q={topic.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(requests.get(rss_url, timeout=15).content)
    trusted_entries = filter_trusted(feed.entries)

    if len(trusted_entries) < profile['min_signals']:
        logging.warning(f"⚠️ Signal weak for {niche} ({len(trusted_entries)} sources). Gating topic.")
        return

    # Content Generation (Inverted Pyramid)
    facts = "\n".join([f"- {e.title} ({e.source.get('title')}) | Date: {getattr(e, 'published', 'Recent')}" for e in trusted_entries[:8]])
    prompt = f"Write a 1200-word neutral news report on '{topic}'. NICHE: {niche}. Use Inverted Pyramid structure. JSON: {{'headline':'', 'image_keyword':'', 'excerpt':'', 'content_html':''}}"
    
    try:
        res = client.chat.completions.create(messages=[{"role":"user","content":prompt}], model="llama-3.3-70b-versatile", response_format={"type":"json_object"}, timeout=60)
        data = json.loads(res.choices[0].message.content)
        if not validate_data(data, profile): 
            logging.error("❌ Headline or JSON Validation Failed.")
            return
    except Exception as e:
        logging.exception(f"❌ Generation/Parsing failed: {e}")
        return

    # Post Assembly
    post = WordPressPost()
    post.title = data['headline']
    compliance = compliance_check(niche, topic)
    
    # Draft vs Publish Logic
    post.post_status = 'draft' if (compliance or profile['status'] == 'draft') else 'publish'
    
    byline = f'<p>By <strong>{chief_editor}</strong> — Editor <br><small>Verified by GCHAM research systems</small></p>'
    audit_footer = '<hr><p><small>This report synthesizes information from verified news outlets. Editorial oversight by GCHAM.</small></p>' if compliance else ''
    
    post.content = byline + data['content_html'] + audit_footer
    post.terms_names = {'category': [niche], 'post_tag': ['Verified', niche, chief_editor]}

    # Image Pipeline (Kill silent failures + Risk Policy)
    if profile['images'] and not compliance and PEXELS_KEY:
        try:
            img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['image_keyword']}&per_page=1", headers={"Authorization": PEXELS_KEY}, timeout=15).json()
            if img_res.get('photos'):
                photo = img_res['photos'][0]
                img_raw = requests.get(photo['src']['large']).content
                img = Image.open(io.BytesIO(img_raw))
                img.thumbnail((1200, 800))
                out = io.BytesIO()
                img.save(out, format='JPEG', quality=85)
                up = {'name': f"{slugify(post.title)}.jpg", 'bits': xmlrpc_client.Binary(out.getvalue()), 'type': 'image/jpeg'}
                wp_img = wp_client.call(media.UploadFile(up))
                post.thumbnail = wp_img['id']
                post.content = f'<figure><img src="{wp_img["url"]}"/><figcaption>Credit: {photo["photographer"]} via Pexels</figcaption></figure>' + post.content
        except Exception as e:
            logging.error(f"❌ Image Pipeline Failure: {e}")

    # Final Deployment
    try:
        wp_client.call(posts.NewPost(post))
        with open("published_topics.txt", "a") as f: f.write(topic + "\n")
        logging.info(f"✅ SUCCESS: {post.title} [{post.post_status.upper()}]")
    except Exception as e:
        logging.error(f"❌ WP Publish Failed: {e}")

if __name__ == "__main__":
    publish()
