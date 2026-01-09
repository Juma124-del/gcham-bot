import os, json, re, random, logging, feedparser, requests, io
from PIL import Image
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client
from python_slugify import slugify
from tenacity import retry, stop_after_attempt, wait_fixed

# --- CONFIG & AUTH ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

client = Groq(api_key=GROQ_API_KEY)
wp_client = Client(WP_URL, WP_USER, WP_PASS)

# --- EDITORIAL GOVERNOR & MEMORY ---
def editorial_governor(signal_count, niche, topic, log_file="published_topics.txt"):
    """Decision System: Checks memory and scores confidence before publishing."""
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            if topic.lower() in f.read().lower():
                logging.warning(f"🛑 Already published: {topic}")
                return False

    # Score Logic: Politics/Economy need more proof than Entertainment
    base_score = min(signal_count * 20, 100)
    risk_penalty = 30 if niche in ["USA Politics", "US Economy"] else 0
    final_score = base_score - risk_penalty
    
    if final_score >= 60:
        with open(log_file, "a") as f: f.write(topic + "\n")
        return True
    return False

# --- CONTENT VIBE ENGINE ---
def get_vibe_and_style(niche):
    """Adjusts tone to be Informative, Entertaining, or Educational."""
    if niche == "Entertainment":
        return "Witty, engaging, and pop-culture savvy.", "Magazine Feature Style"
    elif niche == "Sports":
        return "Energetic, fast-paced, and stats-heavy.", "Match Report Style"
    elif niche == "Educational":
        return "Helpful, authoritative, and instructional.", "Step-by-Step Guide"
    return "Neutral, objective, and journalistic.", "Inverted Pyramid"

# --- CORE FUNCTIONS ---
def ping_google_sitemap():
    sitemap_url = WP_URL.replace('/xmlrpc.php', '/sitemap_index.xml')
    try: requests.get(f"https://www.google.com/ping?sitemap={sitemap_url}", timeout=10)
    except: pass

def research_topic(topic):
    search_query = topic.replace(" ", "+")
    rss_url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"
    try:
        res = requests.get(rss_url, timeout=10)
        feed = feedparser.parse(res.content)
        return feed.entries
    except: return []

def generate_content(topic, niche, facts_text):
    vibe, style = get_vibe_and_style(niche)
    word_count = random.randint(900, 1400)
    prompt = f"""
    Act as a lead writer for GCHAM. Write a {word_count}-word piece: '{topic}'.
    NICHE: {niche} | VIBE: {vibe} | STYLE: {style}
    FACTS: {facts_text}
    
    RULES: No fake quotes. Use h2/h3 tags. Include 3 'People Also Ask' FAQs at the end.
    JSON ONLY: {{"headline":"", "image_keyword":"", "excerpt":"", "content_html":""}}
    """
    try:
        res = client.chat.completions.create(messages=[{"role":"user","content":prompt}], model="llama-3.3-70b-versatile", response_format={"type":"json_object"})
        data = json.loads(re.sub(r'```json|```', '', res.choices[0].message.content).strip())
        # Basic HTML Sanitization
        data['content_html'] = re.sub(r'<(script|style).*?>.*?</\1>', '', data['content_html'], flags=re.DOTALL)
        return data
    except: return None

# --- MAIN EXECUTION ---
def publish():
    logging.info("🚀 GCHAM Global News Engine: ACTIVE")
    chief_editor = "Brayan Juma"
    
    # Selection of Pillars
    niche = random.choice(["US Economy", "Tech News", "USA Politics", "Entertainment", "Sports", "Educational"])
    
    topic_res = client.chat.completions.create(messages=[{"role":"user","content":f"One trending USA headline for {niche}. Title only."}], model="llama-3.3-70b-versatile")
    topic = topic_res.choices[0].message.content.strip().replace('"', '')

    # Step 1: Research & Gating
    entries = research_topic(topic)
    if not editorial_governor(len(entries), niche, topic):
        logging.warning("Gated: Topic did not meet confidence threshold.")
        return

    facts_text = "\n".join([f"- {e.title} ({e.source.get('title')})" for e in entries[:8]])
    
    # Step 2: Content Generation
    data = generate_content(topic, niche, facts_text)
    if not data: return

    # Step 3: WordPress Construction
    post = WordPressPost()
    post.title = data['headline']
    
    # Human Authority Byline
    byline = f'<div style="border-bottom:2px solid #333;margin-bottom:20px;"><strong>Chief Editor:</strong> {chief_editor}</div>'
    post.content = byline + data['content_html']
    post.excerpt = data['excerpt']
    post.post_status = 'publish'
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', niche, chief_editor]}

    # Step 4: Media Optimization
    if PEXELS_KEY:
        try:
            img_res = requests.get(f"https://api.pexels.com/v1/search?query={data['image_keyword']}&per_page=1", headers={"Authorization": PEXELS_KEY}).json()
            if img_res.get('photos'):
                photo = img_res['photos'][0]
                img_raw = requests.get(photo['src']['large']).content
                img = Image.open(io.BytesIO(img_raw))
                img.thumbnail((1200, 800))
                out = io.BytesIO()
                img.save(out, format='JPEG', quality=85)
                
                up = {'name': f"{slugify(post.title)}.jpg", 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(out.getvalue())}
                wp_img = wp_client.call(media.UploadFile(up))
                post.thumbnail = wp_img['id']
                post.content = f'<figure><img src="{wp_img["url"]}"/><figcaption>Credit: {photo["photographer"]} via Pexels</figcaption></figure>' + post.content
        except: pass

    # Step 5: Push Live
    try:
        wp_client.call(posts.NewPost(post))
        logging.info(f"✅ SUCCESS: '{post.title}' is live. Editor: {chief_editor}")
        ping_google_sitemap()
    except Exception as e: logging.error(f"Failed: {e}")

if __name__ == "__main__":
    publish()
