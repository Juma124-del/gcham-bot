import os, json, random, requests, logging, time, ccxt
from datetime import datetime
from groq import Groq
from tavily import TavilyClient
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# ==========================================
# 🛡️ SECTION 1: CONFIG (REFINED)
# ==========================================
class Config:
    VERSION = "GCHAM v7.5 - Global Elite"
    AUTHOR_NAME = "Brayan Juma Okumu"
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    # API Keys from your environment
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    PEXELS_KEY = os.getenv("PEXELS_API_KEY")
    WP_URL = os.getenv("WP_URL")  
    WP_USER = os.getenv("WP_USER")
    WP_PASS = os.getenv("WP_PASS")

# ==========================================
# 📈 NEW: LIVE DATA ENGINE (The A+ Edge)
# ==========================================
def get_live_market_data():
    """Pulls real 2026 prices to insert into articles for authority."""
    try:
        exchange = ccxt.binance()
        btc = exchange.fetch_ticker('BTC/USDT')['last']
        eth = exchange.fetch_ticker('ETH/USDT')['last']
        return f"BTC: ${btc:,.2f} | ETH: ${eth:,.2f}"
    except:
        return "Market data stabilizing..."

# ==========================================
# ✍️ SECTION 3: PUBLISHING (GLOBAL & INVESTIGATIVE)
# ==========================================
def publish():
    logging.basicConfig(level=logging.INFO)
    
    # Expand niches to include your new Global Targets
    niche_focus = random.choice([
        "USA: Trump-Xi Trade War & Tariffs",
        "France: Macron's Nuclear Sovereignty & EU Defense",
        "Global Crypto: Institutional Capital Flight",
        "Economic Impact: Middle East Conflict & Oil Spikes"
    ])
    
    market_stats = get_live_market_data()
    
    try:
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        # 2. RESEARCH (Now focusing on USA, France, and Finance)
        logging.info(f"🔎 GCHAM Deep Research: {niche_focus}...")
        search = tavily.search(query=f"latest news {niche_focus} {Config.CURRENT_DATE}", search_depth="advanced")
        context = "\n".join([f"Source: {r['url']} | Content: {r['content']}" for r in search['results']])

        # 3. AI WRITER (Upgraded to Investigative 1800 words)
        writer_prompt = f"""
        Return ONLY a JSON object. No chatter.
        Topic: {niche_focus}. Current Market: {market_stats}.
        Context: {context}
        Output:
        'headline': Dramatic, professional, high-CTR headline (14 words).
        'body': 1800-word investigative report in HTML. 
        MANDATORY: Use H2/H3 tags. Include the live market data ({market_stats}) in the first paragraph.
        Incorporate geopolitical ties between USA, France, and Global Markets.
        """
        
        chat_completion = groq.chat.completions.create(
            messages=[{"role": "user", "content": writer_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        draft = json.loads(chat_completion.choices[0].message.content)

        # 4. AI EDITOR (The Humanizer)
        edit_completion = groq.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are the Editor-in-Chief. Remove all AI cliches. Output ONLY the polished HTML body."},
                {"role": "user", "content": f"Rewrite for a global elite audience. Keep HTML: {draft['body']}"}
            ],
            model="llama-3.3-70b-versatile"
        )
        final_body = edit_completion.choices[0].message.content

        # 5. AUTHOR EEAT SIGNALS
        author_header = f"""
        <div style="border-left: 5px solid #d4af37; padding: 15px; background: #1a1a1a; color: #fff;">
            <p><strong>GCHAM SPECIAL REPORT | By {Config.AUTHOR_NAME}</strong><br>
            Global Geopolitical Strategist<br>
            {Config.CURRENT_DATE} | {market_stats}</p>
        </div><hr>
        """

        # 6. ASSEMBLE & UPLOAD
        post = WordPressPost()
        post.title = draft['headline']
        post.content = author_header + final_body + f"<hr><h3>About Brayan Juma Okumu</h3><p>{Config.AUTHOR_NAME} is the visionary behind GCHAM...</p>"
        post.post_status = 'draft' # Safety first for AdSense!
        
        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM SUCCESS: A+ Investigative Report {post_id} uploaded to Hostinger.")

    except Exception as e:
        logging.error(f"❌ Error: {e}")

if __name__ == "__main__":
    publish()
