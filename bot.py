import os, json, random, requests, logging, time, ccxt
from datetime import datetime
from groq import Groq
from tavily import TavilyClient
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# ==========================================
# 🛡️ SECTION 1: GLOBAL CONFIG
# ==========================================
class Config:
    AUTHOR_NAME = "Brayan Juma Okumu"
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    PEXELS_KEY = os.getenv("PEXELS_API_KEY")
    WP_URL = os.getenv("WP_URL")  
    WP_USER = os.getenv("WP_USER")
    WP_PASS = os.getenv("WP_PASS")

# ==========================================
# 📸 SECTION 2: IMAGE & CITATION ENGINE
# ==========================================
def get_and_upload_image(keyword, wp_client):
    if not Config.PEXELS_KEY: return None, ""
    headers = {"Authorization": Config.PEXELS_KEY}
    url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=1"
    try:
        res = requests.get(url, headers=headers).json()
        if not res.get('photos'): return None, ""
        photo = res['photos'][0]
        img_url, photographer, pexels_url = photo['src']['large'], photo['photographer'], photo['url']
        citation = f'<figcaption style="font-size:12px; color:#777; margin-top:5px;">Photo by <a href="{pexels_url}" target="_blank">{photographer}</a> via Pexels</figcaption>'
        img_data = requests.get(img_url).content
        filename = f"gcham_media_{int(time.time())}.jpg"
        data = {'name': filename, 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(img_data), 'overwrite': True}
        upload = wp_client.call(media.UploadFile(data))
        img_id, img_web_url = upload.get('id'), upload.get('url')
        img_html = f'<figure style="margin:25px 0; text-align:center;"><img src="{img_web_url}" style="width:100%; border-radius:10px;">{citation}</figure>'
        return img_id, img_html
    except: return None, ""

# ==========================================
# 🚀 SECTION 3: THE AUTOMATED NEWSROOM
# ==========================================
def publish():
    logging.basicConfig(level=logging.INFO)
    categories = ["Politics", "Economics", "Sports", "Entertainment"]
    niche = random.choice(categories)
    
    try:
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        # 1. LIVE DATA
        exchange = ccxt.binance()
        mkt = f"BTC: ${exchange.fetch_ticker('BTC/USDT')['last']:,.0f} | ETH: ${exchange.fetch_ticker('ETH/USDT')['last']:,.0f} | XRP: ${exchange.fetch_ticker('XRP/USDT')['last']:,.4f}"

        # 2. SEARCH TRENDING (USA/FRANCE)
        query = f"trending news {niche} USA France {Config.CURRENT_DATE}"
        logging.info(f"🔎 GCHAM Researching: {query}")
        search = tavily.search(query=query, search_depth="advanced")
        context = "\n".join([r['content'] for r in search['results']])

        # 3. AI WRITING (Strict SEO Output)
        writer_prompt = f"""
        Return ONLY JSON. Topic: {niche}. Context: {context}. Data: {mkt}. 
        Fields: 'headline', 'body' (1500 words HTML), 'img_kw', 'meta', 'tags' (list of 5 tags).
        Target high SEO visibility in USA and France.
        """
        completion = groq.chat.completions.create(messages=[{"role":"user","content":writer_prompt}], model="llama-3.3-70b-versatile", response_format={"type":"json_object"})
        data = json.loads(completion.choices[0].message.content)

        # 4. IMAGE PHASE
        img_id, img_html = get_and_upload_image(data.get('img_kw', niche), wp)

        # 5. HEADERS & BIOS
        author_header = f'<div style="border-left:4px solid #333; padding-left:15px; margin-bottom:25px;"><p><strong>By {Config.AUTHOR_NAME}</strong><br>Editor-in-Chief | GCHAM Newsroom<br>{Config.CURRENT_DATE} | {mkt}</p></div><hr>'
        author_bio = f'<hr><div style="margin-top:40px; padding:25px; background:#f9f9f9; border-radius:8px;"><h3>About the Author</h3><p><strong>{Config.AUTHOR_NAME}</strong> is the founder of GCHAM, tracking 2026 global shifts in USA and France.</p></div>'

        # 6. SEO ASSEMBLY & PUBLISH
        post = WordPressPost()
        post.title = data.get('headline')
        post.content = author_header + img_html + data.get('body') + author_bio
        
        # Tags and Categories
        post.terms_names = {
            'post_tag': data.get('tags', [niche, 'GCHAM', 'Trending']),
            'category': [niche]
        }

        # RankMath SEO Fields (Critical for Google)
        post.custom_fields = [
            {'key': '_rank_math_title', 'value': data.get('headline')},
            {'key': '_rank_math_description', 'value': data.get('meta')},
            {'key': '_rank_math_focus_keyword', 'value': data.get('img_kw')}
        ]

        post.post_status = 'publish' 
        if img_id: post.thumbnail = img_id
        
        wp.call(posts.NewPost(post))
        logging.info(f"🚀 GCHAM SEO-LIVE: Published {niche} article by {Config.AUTHOR_NAME}.")

    except Exception as e: logging.error(f"❌ Error: {e}")

if __name__ == "__main__":
    publish()
