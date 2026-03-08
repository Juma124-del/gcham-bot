import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from tavily import TavilyClient
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# ==========================================
# 🛡️ SECTION 1: CONFIG
# ==========================================
class Config:
    VERSION = "GCHAM Empire Shield v7.2"
    AUTHOR_NAME = "Brayan Juma Okumu"
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    PEXELS_KEY = os.getenv("PEXELS_API_KEY")
    WP_URL = os.getenv("WP_URL")  
    WP_USER = os.getenv("WP_USER")
    WP_PASS = os.getenv("WP_PASS")

# ==========================================
# 📸 SECTION 2: IMAGE LOGIC
# ==========================================
def get_and_upload_image(keyword, wp_client):
    if not Config.PEXELS_KEY: 
        return None
    headers = {"Authorization": Config.PEXELS_KEY}
    url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=1"
    try:
        res = requests.get(url, headers=headers).json()
        if not res.get('photos'): return None
        img_url = res['photos'][0]['src']['large']
        img_data = requests.get(img_url).content
        filename = f"gcham_{int(time.time())}.jpg"
        data = {
            'name': filename,
            'type': 'image/jpeg',
            'bits': xmlrpc_client.Binary(img_data),
            'overwrite': True
        }
        upload = wp_client.call(media.UploadFile(data))
        return upload.get('id') 
    except Exception as e:
        logging.error(f"❌ Image Error: {e}")
        return None

# ==========================================
# ✍️ SECTION 3: PUBLISHING (STRICT SEO VERSION)
# ==========================================
def publish():
    logging.basicConfig(level=logging.INFO)
    # UPDATED NICHES FOR MARCH 8, 2026
    niche = random.choice([
        "Global Economy (China NPC 2026)", 
        "Middle East Geopolitics", 
        "International Women's Day 2026", 
        "AI Transformation & Jobs", 
        "Crypto Market Volatility"
    ])
    
    try:
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        # 2. RESEARCH PHASE
        logging.info(f"🔎 GCHAM Researching Trending: {niche}...")
        search = tavily.search(query=f"breaking news {niche} {Config.CURRENT_DATE}", search_depth="advanced")
        context = "\n".join([f"Source: {r['url']} | Content: {r['content']}" for r in search['results']])

        # 3. AI WRITER PHASE (Strict JSON)
        logging.info(f"🧠 AI Drafting 1600-word investigative report...")
        writer_prompt = f"""
        Return ONLY a JSON object. No intro/outro. 
        Topic: {niche}. Date: {Config.CURRENT_DATE}. Context: {context}.
        Include:
        'headline': 12-16 word viral, professional headline.
        'meta_desc': 155 character SEO description.
        'image_kw': 3 keywords for high-quality Pexels search.
        'tags': 5 tags including 'GCHAM', '2026 Global News', and niche keywords.
        'body': Write a 1600-word deep investigative report in HTML. 
        Structure: H2 Intro, H2 Key Takeaways (Bullet points), H3 Analysis, H3 Global Impact, H2 Conclusion.
        """
        
        chat_completion = groq.chat.completions.create(
            messages=[{"role": "user", "content": writer_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        draft_data = json.loads(chat_completion.choices[0].message.content)
        raw_content = draft_data.get('body')

        # 4. AI EDITOR PHASE (The "Strict Mode" Fix)
        logging.info(f"📝 AI Editor humanizing and removing AI-isms...")
        edit_completion = groq.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a Senior Editor at Bloomberg. You only output the final edited HTML. Never speak to the user. No 'Here is your article' or 'I have magic' phrases."},
                {"role": "user", "content": f"Humanize this report, improve flow, and remove all AI cliches. Keep HTML tags: {raw_content}"}
            ],
            model="llama-3.3-70b-versatile"
        )
        final_body = edit_completion.choices[0].message.content

        # 5. ASSEMBLE (E-E-A-T INTEGRATION)
        author_header = f"""
        <p><strong>By {Config.AUTHOR_NAME}</strong><br>
        <em>Editor-in-Chief | GCHAM Empire News</em><br>
        Published: {Config.CURRENT_DATE}</p><hr>
        """
        
        author_bio = f"""
        <hr><div style="background:#f9f9f9; padding:20px; border-radius:5px;">
        <h3>About {Config.AUTHOR_NAME}</h3>
        <p>Brayan Juma Okumu is the founder of GCHAM, a global news hub analyzing the 2026 economic shifts and geopolitics.</p>
        </div>
        """

        # 6. UPLOAD
        post = WordPressPost()
        post.title = draft_data.get('headline')
        post.content = author_header + final_body + author_bio
        post.excerpt = draft_data.get('meta_desc')
        post.post_status = 'draft'
        post.terms_names = {'category': [niche.split(' (')[0]], 'post_tag': draft_data.get('tags')}
        
        image_id = get_and_upload_image(draft_data.get('image_kw'), wp)
        if image_id: post.thumbnail = image_id 
            
        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM SUCCESS: Post {post_id} is live as a DRAFT.")

    except Exception as e:
        logging.error(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    publish()
