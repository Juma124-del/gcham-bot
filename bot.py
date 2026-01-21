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
    VERSION = "GCHAM Empire Shield v6.7"
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
    """Searches Pexels and uploads to WP Media Library"""
    if not Config.PEXELS_KEY: 
        logging.warning("⚠️ Pexels Key missing. Skipping image.")
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
# ✍️ SECTION 3: PUBLISHING (Fixed & 2026 Ready)
# ==========================================
def publish():
    logging.basicConfig(level=logging.INFO)
    niche = random.choice(["USA Politics", "Global Economics", "Professional Sports", "Crypto Markets", "Entertainment News"])
    
    try:
        # 1. INITIALIZE CLIENTS
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        # 2. RESEARCH PHASE
        logging.info(f"🔎 GCHAM Researching: {niche}...")
        search = tavily.search(query=f"latest {niche} news {Config.CURRENT_DATE}", search_depth="advanced")
        context = "\n".join([f"- {r['content']}" for r in search['results']])

        # 3. AI GENERATION PHASE (Updated Model)
        logging.info(f"🧠 AI Generating 1500-word report for {niche}...")
        prompt = f"""
        Return ONLY a JSON object for a news report on {niche}.
        Include:
        'headline': A viral, professional headline.
        'image_kw': 2-3 keywords for a Pexels image search.
        'body': 1500 words of deep investigative content. Use H2 and H3 tags for structure. Based on this context: {context}
        """
        
        chat_completion = groq.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-specdec", # ✅ UPDATED TO ACTIVE 2026 MODEL
            response_format={"type": "json_object"}
        )
        
        # Parse the JSON response
        data = json.loads(chat_completion.choices[0].message.content)
        final_content = data.get('body')

        # 4. IMAGE PHASE
        image_id = get_and_upload_image(data.get('image_kw', niche), wp)
        
        # 5. ASSEMBLE & UPLOAD
        post = WordPressPost()
        post.title = data.get('headline')
        post.content = final_content
        post.post_status = 'publish'
        post.terms_names = {
            'category': [niche],
            'post_tag': [niche, 'GCHAM', '2026 News', 'AI Generated']
        }
        
        if image_id:
            post.thumbnail = image_id 
            
        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM SUCCESS: Post {post_id} live on World of Vitimbi!")

    except Exception as e:
        logging.error(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    publish()
