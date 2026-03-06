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
    VERSION = "GCHAM Autonomous Newsroom v7.0"
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
# ✍️ SECTION 3: PUBLISHING (V7.0 UPGRADED)
# ==========================================
def publish():
    logging.basicConfig(level=logging.INFO)
    niche = random.choice(["USA Politics", "Global Economics", "Professional Sports", "Crypto Markets", "Entertainment News"])
    
    try:
        # 1. INITIALIZE CLIENTS
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        # 2. RESEARCH PHASE (Enhanced Context)
        logging.info(f"🔎 GCHAM Researching: {niche}...")
        search = tavily.search(query=f"latest {niche} news {Config.CURRENT_DATE}", search_depth="advanced")
        context = "\n".join([f"Source: {r['url']} | Summary: {r['content']}" for r in search['results']])

        # 3. AI WRITER PHASE (SEO & Structure Focused)
        logging.info(f"🧠 AI Drafting report for {niche}...")
        writer_prompt = f"""
        Return ONLY a JSON object for a professional news investigation.
        Include:
        'headline': Viral Discover-optimized headline (12-16 words).
        'meta_description': SEO summary (155 chars).
        'image_kw': 3 keywords for Pexels.
        'seo_tags': 5 relevant tags.
        'body': Write a 1600-word investigative report in HTML. 
        Use H2 and H3 tags. Structure: Intro -> Key Takeaways (list) -> Detailed Analysis -> Economic Impact -> Conclusion.
        Based on this context: {context}
        """
        
        chat_completion = groq.chat.completions.create(
            messages=[{"role": "user", "content": writer_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        
        draft_data = json.loads(chat_completion.choices[0].message.content)

        # 4. AI EDITOR PHASE (Humanizing the Tone)
        logging.info(f"📝 AI Editor humanizing the content...")
        editor_prompt = f"""
        You are a Senior Editor at Bloomberg. Rewrite the following article to sound more human, 
        improve flow, and remove AI-typical clichés. Keep the HTML structure intact.
        Article: {draft_data.get('body')}
        """
        
        edit_completion = groq.chat.completions.create(
            messages=[{"role": "user", "content": editor_prompt}],
            model="llama-3.3-70b-versatile"
        )
        humanized_content = edit_completion.choices[0].message.content

        # 5. IMAGE PHASE
        image_id = get_and_upload_image(draft_data.get('image_kw', niche), wp)
        
        # 6. ASSEMBLE & UPLOAD (With E-E-A-T Signals)
        author_header = f"""
        <p><strong>By {Config.AUTHOR_NAME}</strong><br>
        Editor | GCHAM Global Newsroom<br>
        Published: {Config.CURRENT_DATE}</p><hr>
        """
        
        author_bio = f"""
        <hr><h3>About the Author</h3>
        <p><strong>{Config.AUTHOR_NAME}</strong> is the founder and editor of GCHAM, covering geopolitics, economics, and technology for a global audience.</p>
        """

        post = WordPressPost()
        post.title = draft_data.get('headline')
        post.content = author_header + humanized_body + author_bio
        post.excerpt = draft_data.get('meta_description')
        post.post_status = 'draft'  # Change to 'publish' only after AdSense approval
        
        post.terms_names = {
            'category': [niche],
            'post_tag': draft_data.get('seo_tags', [niche, 'GCHAM'])
        }
        
        # SEO Custom Fields (RankMath)
        post.custom_fields = [
            {'key': 'rank_math_description', 'value': draft_data.get('meta_description')}
        ]
        
        if image_id:
            post.thumbnail = image_id 
            
        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ SUCCESS: GCHAM v7 uploaded Post {post_id} to DRAFTS.")

    except Exception as e:
        logging.error(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    publish()
