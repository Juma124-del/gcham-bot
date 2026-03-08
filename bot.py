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
# 📈 ROBUST MARKET DATA
# ==========================================
def get_live_market_data():
    exchanges = ['kraken', 'coinbasepro', 'okx']
    for ex in exchanges:
        try:
            exch = getattr(ccxt, ex)()
            btc = exch.fetch_ticker('BTC/USD')['last']
            eth = exch.fetch_ticker('ETH/USD')['last']
            return f"BTC: ${btc:,.0f} | ETH: ${eth:,.0f} (via {ex.upper()})"
        except: continue
    return "Market Status: Highly Volatile"

# ==========================================
# 📸 IMAGE ENGINE (CENTRAL ALIGNMENT FIX)
# ==========================================
def get_and_upload_image(keyword, wp_client):
    if not Config.PEXELS_KEY: return None, ""
    headers = {"Authorization": Config.PEXELS_KEY}
    url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=1"
    try:
        res = requests.get(url, headers=headers).json()
        if not res.get('photos'): return None, ""
        photo = res['photos'][0]
        img_url, photog, p_url = photo['src']['large'], photo['photographer'], photo['url']
        
        # Centered Image with proper CSS
        citation = f'<figcaption style="font-size:13px; color:#666; margin-top:8px;">Photo by <a href="{p_url}" target="_blank" style="color:#666;">{photog}</a> via Pexels</figcaption>'
        img_data = requests.get(img_url).content
        filename = f"gcham_{int(time.time())}.jpg"
        data = {'name': filename, 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(img_data), 'overwrite': True}
        upload = wp_client.call(media.UploadFile(data))
        
        img_html = f'<div style="text-align:center; margin:30px 0;"><img src="{upload["url"]}" style="width:100%; max-width:800px; border-radius:8px; display:block; margin:0 auto;">{citation}</div>'
        return upload['id'], img_html
    except: return None, ""

# ==========================================
# 🚀 THE CLEAN NEWSROOM
# ==========================================
def publish():
    logging.basicConfig(level=logging.INFO)
    niche = random.choice(["Politics", "Economics", "Sports", "Entertainment"])
    
    try:
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        mkt = get_live_market_data()
        query = f"breaking news {niche} USA France {Config.CURRENT_DATE}"
        search = tavily.search(query=query, search_depth="advanced")
        context = "\n".join([r['content'] for r in search['results']])

        # CRUCIAL: Instruct AI to output CLEAN HTML PARAGRAPHS, NOT JSON in the body
        writer_prompt = f"""
        Return ONLY a JSON object. Topic: {niche}. Data: {mkt}. Context: {context}.
        Fields to include: 
        1. 'headline': Strong SEO Title.
        2. 'body': Professional news article in CLEAN HTML. NO JSON OBJECTS INSIDE. 
           Use <p> for paragraphs. Use <h2> and <h3> for headers. Use the INVERTED PYRAMID.
        3. 'meta': 160 char summary.
        4. 'img_kw': Image keyword.
        5. 'tags': List of 5 strings.
        """
        
        completion = groq.chat.completions.create(messages=[{"role":"user","content":writer_prompt}], model="llama-3.3-70b-versatile", response_format={"type":"json_object"})
        data = json.loads(completion.choices[0].message.content)

        # Process Tags
        tags = [str(t) for t in data.get('tags', [niche, 'GCHAM'])]

        # Featured Image & Body Image Logic
        img_id, img_html = get_and_upload_image(data.get('img_kw', niche), wp)

        # Professional Layout Assembly
        header = f'<div style="border-bottom:3px solid #000; padding-bottom:10px; margin-bottom:20px;"><p style="margin:0;"><strong>By {Config.AUTHOR_NAME}</strong></p><p style="margin:0; font-size:14px; color:#555;">Editor-in-Chief | {Config.CURRENT_DATE} | {mkt}</p></div>'
        
        bio = f'<hr style="margin-top:50px;"><div style="background:#f4f4f4; padding:20px; border-radius:10px;"><h3>About the Author</h3><p><strong>{Config.AUTHOR_NAME}</strong> is the founder of GCHAM Global Intelligence, covering high-stakes trends in the USA and France.</p></div>'

        # ASSEMBLE POST
        post = WordPressPost()
        post.title = data.get('headline')
        # Combine everything into one clean HTML string
        post.content = header + img_html + data.get('body') + bio
        
        post.terms_names = {'post_tag': tags, 'category': [niche]}
        post.custom_fields = [
            {'key': '_rank_math_title', 'value': data.get('headline')},
            {'key': '_rank_math_description', 'value': data.get('meta')},
            {'key': '_rank_math_focus_keyword', 'value': data.get('img_kw')}
        ]
        post.post_status = 'publish'
        if img_id: post.thumbnail = img_id # Set the featured image
        
        wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM CLEAN-LIVE: {niche} article published.")

    except Exception as e: logging.error(f"❌ Error: {e}")

if __name__ == "__main__":
    publish()
