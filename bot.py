import os, json, random, requests, logging, time
from datetime import datetime
from groq import Groq
from tavily import TavilyClient
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client
from pytrends.request import TrendReq 

# ==========================================
# 🛡️ SECTION 1: CONFIG & IDENTITY
# ==========================================
class Config:
    AUTHOR_NAME = "Brayan Juma Okumu"
    SITE_NAME = "GCHAM Empire"
    GEOGRAPHY = "Worldwide (Global News)" 

    GROQ_KEY = os.environ.get("GROQ_API_KEY")
    TAVILY_KEY = os.environ.get("TAVILY_API_KEY")
    PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
    WP_URL = os.environ.get("WP_URL")
    WP_USER = os.environ.get("WP_USER")
    WP_PASS = os.environ.get("WP_PASS")

# ==========================================
# 🔥 SECTION 2: FAIL-SAFE TREND SCOUTING
# ==========================================
def get_trending_topics(tavily_client):
    try:
        # 1. Attempt Google Trends
        logging.info("📡 Attempting Google Trends...")
        pytrends = TrendReq(hl='en-US', tz=360)
        trending = pytrends.trending_searches(pn='united_states')
        return trending[0].tolist()[:10]
    except Exception as e:
        # 2. If it fails (Exit Code 1 prevention), use Tavily
        logging.warning(f"⚠️ Google Trends blocked: {e}. Switching to Tavily Live Scouting...")
        try:
            search = tavily_client.search(
                query="top global news headlines today March 2026", 
                search_depth="basic"
            )
            return [r['title'] for r in search['results'][:10]]
        except:
            # 3. Last resort fallback (Never let the bot die)
            logging.error("🚨 Both Trends and Tavily failed. Using hardcoded emergency topics.")
            return ["Global Economic Shift", "World Politics 2026", "Crypto Markets Update", "International Sports Highlights"]

# ==========================================
# 🔗 SECTION 3: INTERNAL LINKING & SEO
# ==========================================
def add_internal_links(content):
    links = [
        ("global economy", "https://gcham.com/category/economics"),
        ("breaking news", "https://gcham.com"),
        ("football", "https://gcham.com/category/sports"),
        ("crypto", "https://gcham.com/category/crypto"),
    ]
    for keyword, url in links:
        if keyword in content.lower():
            content = content.replace(keyword, f'<a href="{url}">{keyword}</a>', 1)
    return content

# ==========================================
# 📸 SECTION 4: IMAGE HANDLER (SEO SAFE)
# ==========================================
def get_and_upload_image(keyword, wp_client):
    if not Config.PEXELS_KEY: return None, None
    headers = {"Authorization": Config.PEXELS_KEY}
    url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=1"
    try:
        res = requests.get(url, headers=headers).json()
        if not res.get('photos'): return None, None
        photo = res['photos'][0]
        img_url = photo['src']['large']
        data = {
            'name': f"gcham_{int(time.time())}.jpg",
            'type': 'image/jpeg',
            'bits': xmlrpc_client.Binary(requests.get(img_url).content),
            'caption': f"{keyword} - Photo via Pexels for GCHAM",
            'description': keyword,  # SEO ALT TEXT
            'overwrite': True
        }
        upload = wp_client.call(media.UploadFile(data))
        return upload.get('id'), f"Visual representation of {keyword}"
    except: return None, None

# ==========================================
# ✍️ SECTION 5: THE ANTI-HALLUCINATION WRITER
# ==========================================
def write_global_report(groq, topic, context, target_words):
    writer_prompt = f"""
    Return ONLY a JSON object. You are a Senior Investigative Journalist for GCHAM Empire.
    
    TOPIC: {topic}
    FACTUAL CONTEXT: {context}
    TARGET: {target_words} words.

    🛡️ ANTI-HALLUCINATION RULES:
    - DO NOT invent facts, quotes, or statistics.
    - Only use information from the provided CONTEXT.
    - If uncertain, say "reports suggest" instead of guessing.

    🚫 ANTI-LAZY RULES:
    - Avoid "In conclusion" or generic summaries.
    - Each section must add NEW insight or a specific real-world impact.
    - Write for a Worldwide audience (USA, Europe, Africa, Asia).

    OUTPUT FORMAT:
    {{
      "headline": "Viral title",
      "excerpt": "Compelling summary",
      "keywords": "SEO keywords",
      "body": "HTML Content (1200+ words)",
      "category": "Politics, Economics, Sports, or Entertainment",
      "image_kw": "Photography keyword"
    }}
    """
    res = groq.chat.completions.create(
        messages=[{"role": "user", "content": writer_prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        max_tokens=4000
    )
    return json.loads(res.choices[0].message.content)

# ==========================================
# 🚀 SECTION 6: THE PUBLISH ENGINE
# ==========================================
def publish_engine():
    logging.basicConfig(level=logging.INFO)
    try:
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        # 1. Scout Trends (With Fail-Safe)
        trends = get_trending_topics(tavily)
        topic = random.choice(trends)
        logging.info(f"🔥 Active Topic: {topic}")

        # 2. Research & Write
        search = tavily.search(query=f"deep investigative details for {topic} March 2026", search_depth="advanced")
        context = "\n".join([r['content'] for r in search['results']])
        draft = write_global_report(groq, topic, context, random.randint(1200, 1600))
        draft['body'] = add_internal_links(draft['body'])

        # 🛡️ THE SUPPORT BOX (Brayan's Mission)
support_header = """
<div style="background:#f9fbfc; border:1px solid #e1e8ed; padding:30px; border-radius:15px; margin-bottom:35px; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
    <h3 style="margin-top:0; color:#0056b3; font-size:22px; border-bottom:2px solid #0056b3; padding-bottom:10px;">🛡️ Support the GCHAM Empire</h3>
    <p style="color:#444; line-height:1.6; font-size:15px;">
        Our mission is to provide independent, high-standard global reporting across <strong>Politics, Economics, and Sports</strong>. 
        Your support ensures the <strong>GCHAM Empire</strong> remains free and accessible to the whole world.
    </p>
    
    <div style="background:#ffffff; border-left:5px solid #26a17b; padding:15px; margin:20px 0; border-radius:5px;">
        <p style="margin:0; font-weight:bold; color:#26a17b; font-size:14px; text-transform:uppercase;">Donate via USDT (TRC-20 Network):</p>
        <code style="display:block; background:#f4f4f4; padding:12px; margin-top:8px; border-radius:4px; font-size:14px; word-break:break-all; color:#333; border:1px dashed #26a17b;">
            TRxc5kDS89SAXCR8GgGzHXRH4oSjuhBM9T
        </code>
        <p style="margin-top:8px; font-size:12px; color:#666;">⚠️ <em>Please ensure you are using the <strong>TRON (TRC20)</strong> network to avoid loss of funds.</em></p>
    </div>

    <p style="margin-bottom:0; font-size:14px;">
        <strong>✉️ Inquiries & Partnerships:</strong> 
        <a href="mailto:gchamempire@gmail.com" style="color:#0056b3; text-decoration:none; font-weight:bold;">gchamempire@gmail.com</a>
    </p>
</div>
"""
        
        image_id, img_label = get_and_upload_image(draft['image_kw'], wp)
        author_box = f"<hr><p><em>Reported by {Config.AUTHOR_NAME}, Founder of GCHAM Empire.</em></p>"

        full_content = f"{support_header}<p><i>{draft['excerpt']}</i></p>{draft['body']}<br><p style='font-size:10px; color:gray;'>{img_label}</p>{author_box}"

        # 3. Direct Post
        post = WordPressPost()
        post.title = draft['headline']
        post.content = full_content
        post.post_status = 'publish'
        post.terms_names = {'category': [draft['category']], 'post_tag': draft['keywords'].split(',')}
        if image_id: post.thumbnail = image_id
        
        wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM SUCCESS: {topic} is LIVE.")

    except Exception as e:
        logging.error(f"❌ System Error: {e}")

if __name__ == "__main__":
    publish_engine()
