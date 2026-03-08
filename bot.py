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
# 📸 IMAGE ENGINE
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
        citation = f'<figcaption style="font-size:13px; color:#666; margin-top:8px; text-align:center;">Photo by <a href="{p_url}" target="_blank" style="color:#666;">{photog}</a> via Pexels</figcaption>'
        img_data = requests.get(img_url).content
        filename = f"gcham_{int(time.time())}.jpg"
        data = {'name': filename, 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(img_data), 'overwrite': True}
        upload = wp_client.call(media.UploadFile(data))
        img_html = f'<div style="text-align:center; margin:30px 0;"><img src="{upload["url"]}" style="width:100%; max-width:900px; border-radius:10px; box-shadow: 0 10px 30px rgba(0,0,0,0.15);">{citation}</div>'
        return upload['id'], img_html
    except: return None, ""

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
        Return ONLY a JSON object. 
        MANDATORY: Write as a Senior Intelligence Analyst for a global financial newspaper.
        Topic: {niche}. Data: {mkt}. Context: {context}.
        
        STRUCTURE:
        - Lead: A hard-hitting, 3-sentence summary that explains the global impact.
        - Body: 1500 words of deep, investigative prose. Use <h2> and <h3> tags for subheadings.
        - Style: No fluff. Focus on geopolitical strategy, economic shifts, and policy conflict.
        
        Fields: 'headline', 'body', 'meta', 'img_kw', 'tags'.
        """
        
        completion = groq.chat.completions.create(messages=[{"role":"user","content":writer_prompt}], model="llama-3.3-70b-versatile", response_format={"type":"json_object"})
        data = json.loads(completion.choices[0].message.content)

        img_id, img_html = get_and_upload_image(data.get('img_kw', niche), wp)

        # Header Section (Top)
        header = f'''
        <div style="margin-bottom:40px; border-bottom:1px solid #ddd; padding-bottom:10px;">
            <p style="font-size:14px; text-transform:uppercase; letter-spacing:1px; color:#888; margin:0;">{niche} | Investigative Report</p>
            <p style="font-size:14px; color:#555; margin:5px 0;">{Config.CURRENT_DATE} • {mkt}</p>
        </div>
        '''
        
        # Author Section (Footer - Bottom)
        footer_bio = f'''
        <div style="margin-top:60px; padding:30px; background:#f9f9f9; border-top:4px solid #1a1a1a; border-radius: 0 0 8px 8px;">
            <div style="display:flex; align-items:center; gap:20px;">
                <div>
                    <h3 style="margin:0; font-size:22px;">Author: {Config.AUTHOR_NAME}</h3>
                    <p style="margin:5px 0; font-weight:bold; color:#d9534f;">Role: {Config.AUTHOR_ROLE}</p>
                    <p style="margin:10px 0; line-height:1.6;"><strong>Expertise:</strong> {Config.AUTHOR_EXPERTISE}</p>
                    <p style="margin:0; line-height:1.6;"><strong>Experience:</strong> {Config.AUTHOR_EXPERIENCE}</p>
                </div>
            </div>
        </div>
        '''

        # Post Assembly
        post = WordPressPost()
        post.title = data.get('headline')
        post.content = header + img_html + data.get('body') + footer_bio
        post.terms_names = {'post_tag': data.get('tags', [niche]), 'category': [niche]}
        post.custom_fields = [
            {'key': '_rank_math_title', 'value': data.get('headline')},
            {'key': '_rank_math_description', 'value': data.get('meta')},
            {'key': '_rank_math_focus_keyword', 'value': data.get('img_kw')}
        ]
        post.post_status = 'publish'
        if img_id: post.thumbnail = img_id
        
        wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM PREMIER: {niche} article published with Footer Bio.")

    except Exception as e: logging.error(f"❌ Error: {e}")

if __name__ == "__main__":
    publish()
