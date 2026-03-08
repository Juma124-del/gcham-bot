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
    AUTHOR_NAME = "Brayan Juma"
    AUTHOR_ROLE = "Founder & Editor, GCHAM"
    AUTHOR_EXPERTISE = "Global geopolitics, economic trends, and technology policy."
    AUTHOR_EXPERIENCE = "Juma covers international affairs, financial markets, and digital economy developments, providing deep analysis for a global audience."
    
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    PEXELS_KEY = os.getenv("PEXELS_API_KEY")
    WP_URL = os.getenv("WP_URL")  
    WP_USER = os.getenv("WP_USER")
    WP_PASS = os.getenv("WP_PASS")

# ==========================================
# 📈 MARKET DATA ENGINE
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
    return "Market Status: Volatile"

# ==========================================
# 📸 IMAGE ENGINE (CLEAN FEATURED IMAGE ONLY)
# ==========================================
def get_and_upload_image(keyword, wp_client):
    if not Config.PEXELS_KEY: return None
    headers = {"Authorization": Config.PEXELS_KEY}
    url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=1"
    try:
        res = requests.get(url, headers=headers).json()
        if not res.get('photos'): return None
        photo = res['photos'][0]
        img_url = photo['src']['large']
        img_data = requests.get(img_url).content
        filename = f"gcham_{int(time.time())}.jpg"
        data = {'name': filename, 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(img_data), 'overwrite': True}
        upload = wp_client.call(media.UploadFile(data))
        return upload['id'] # Return only ID for Featured Image
    except: return None

# ==========================================
# 🚀 THE GCHAM INTELLIGENCE ENGINE
# ==========================================
def publish():
    logging.basicConfig(level=logging.INFO)
    niche = random.choice(["Politics", "Economics", "Sports", "Entertainment"])
    
    try:
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        mkt = get_live_market_data()
        query = f"breaking investigative news {niche} USA France {Config.CURRENT_DATE}"
        search = tavily.search(query=query, search_depth="advanced")
        context = "\n".join([r['content'] for r in search['results']])

        writer_prompt = f"""
        Return ONLY a JSON object. Topic: {niche}. Data: {mkt}. Context: {context}.
        MANDATORY: 
        1. 'headline' MUST be a plain string.
        2. 'body' MUST be professional HTML with <p>, <h2>, <h3> tags. 
        3. Use the Inverted Pyramid style (Critical info first).
        4. No intro/outro fluff. Start directly with the news.
        Fields: 'headline', 'body', 'meta', 'img_kw', 'tags'.
        """
        
        completion = groq.chat.completions.create(messages=[{"role":"user","content":writer_prompt}], model="llama-3.3-70b-versatile", response_format={"type":"json_object"})
        data = json.loads(completion.choices[0].message.content)

        headline = str(data.get('headline', 'GCHAM Intelligence Report'))
        body_content = str(data.get('body', ''))

        # Get Featured Image ID (Removed img_html from body to prevent duplication)
        img_id = get_and_upload_image(data.get('img_kw', niche), wp)

        # 🏗️ LAYOUT: Top Meta Header
        header = f'''
        <div style="margin-bottom:30px; border-bottom:2px solid #1a1a1a; padding-bottom:15px;">
            <p style="font-size:13px; text-transform:uppercase; font-weight:bold; color:#d9534f; margin:0;">{niche} Intelligence Brief</p>
            <p style="font-size:14px; color:#666; margin:5px 0;">{Config.CURRENT_DATE} | {mkt}</p>
        </div>
        '''
        
        # 🏗️ LAYOUT: Bottom Author Footer
        footer_bio = f'''
        <div style="margin-top:50px; padding:30px; background:#f4f4f4; border-radius:8px; border:1px solid #ddd;">
            <h3 style="margin:0 0 10px 0; font-size:20px; color:#1a1a1a;">Author: {Config.AUTHOR_NAME}</h3>
            <p style="margin:0; font-weight:bold; color:#d9534f; font-size:14px;">{Config.AUTHOR_ROLE}</p>
            <p style="margin:15px 0 0 0; font-size:15px; line-height:1.6; color:#333;"><strong>Expertise:</strong> {Config.AUTHOR_EXPERTISE}</p>
            <p style="margin:10px 0 0 0; font-size:15px; line-height:1.6; color:#333;"><strong>Experience:</strong> {Config.AUTHOR_EXPERIENCE}</p>
        </div>
        '''

        # Assemble Post (Clean: Header + Body + Footer)
        post = WordPressPost()
        post.title = headline
        post.content = header + body_content + footer_bio
        
        # Metadata
        raw_tags = data.get('tags', [niche])
        post.terms_names = {'post_tag': [str(t) for t in raw_tags] if isinstance(raw_tags, list) else [niche], 'category': [niche]}
        
        post.custom_fields = [
            {'key': '_rank_math_title', 'value': headline},
            {'key': '_rank_math_description', 'value': str(data.get('meta', ''))},
            {'key': '_rank_math_focus_keyword', 'value': str(data.get('img_kw', niche))}
        ]
        
        post.post_status = 'publish'
        if img_id: post.thumbnail = img_id # Themes use this as the main top image
        
        wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM SUCCESS: Clean {niche} article published.")

    except Exception as e: logging.error(f"❌ Error: {e}")

if __name__ == "__main__":
    publish()
