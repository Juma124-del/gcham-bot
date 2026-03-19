import os, json, random, requests, logging, time
from datetime import datetime
from groq import Groq
from tavily import TavilyClient
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# ==========================================
# 🛡️ SECTION 1: CONFIG (Safe Connection)
# ==========================================
class Config:
    AUTHOR_NAME = "Brayan Juma Okumu"
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    
    # Using os.environ.get is why your OLD code connected successfully. 
    # It pulls directly from your GitHub Secrets.
    GROQ_KEY = os.environ.get("GROQ_API_KEY")
    TAVILY_KEY = os.environ.get("TAVILY_API_KEY")
    PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
    WP_URL = os.environ.get("WP_URL")  # Ensure this is https://gcham.com/xmlrpc.php
    WP_USER = os.environ.get("WP_USER")
    WP_PASS = os.environ.get("WP_PASS")

# ==========================================
# 📸 SECTION 2: ETHICAL IMAGE LOGIC
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
        photographer = photo['photographer']
        
        caption = f"Visual representation of {keyword}. Credit: {photographer} via Pexels."
        img_data = requests.get(img_url).content
        
        data = {
            'name': f"gcham_{int(time.time())}.jpg",
            'type': 'image/jpeg',
            'bits': xmlrpc_client.Binary(img_data),
            'caption': caption,
            'overwrite': True
        }
        upload = wp_client.call(media.UploadFile(data))
        return upload.get('id'), caption
    except Exception as e:
        logging.error(f"❌ Image Error: {e}")
        return None, None

# ==========================================
# 🌍 SECTION 3: THE GLOBAL SCOUT
# ==========================================
def publish():
    logging.basicConfig(level=logging.INFO)
    try:
        # Initialize with specific timeout to prevent "Network Unreachable"
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        logging.info("🌍 Scouting Global Trends (USA, UK, France, China, Japan)...")
        scout = tavily.search(query="breaking news politics economics 2026", search_depth="advanced")
        trends = "\n".join([f"- {r['title']}" for r in scout['results']])

        decision_msg = groq.chat.completions.create(
            messages=[{"role": "user", "content": f"Pick the #1 most important story from: {trends}. Return ONLY the topic name."}],
            model="llama-3.3-70b-versatile"
        )
        decision = decision_msg.choices[0].message.content.strip()
        logging.info(f"🔥 Chosen Topic: {decision}")

        search = tavily.search(query=f"investigative details and external sources for {decision}", search_depth="advanced")
        sources = "\n".join([f"Source: {r['url']}" for r in search['results'][:3]])
        context = "\n".join([r['content'] for r in search['results']])

        writer_prompt = f"""
        Return ONLY a JSON object. Topic: {decision}. Context: {context}. 
        Sources to cite: {sources}.
        1. 'headline': Viral, journalistic title.
        2. 'excerpt': 2-sentence SEO summary for Google.
        3. 'body': 1600-word investigative report in HTML. 
           - Include 2-3 external links to reputable sources.
           - Use H2 and H3 tags.
        4. 'image_kw': Keyword for Pexels.
        """
        
        response = groq.chat.completions.create(
            messages=[{"role": "user", "content": writer_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            max_tokens=4000
        )
        
        # CLEANING JSON (Safety fix)
        content = response.choices[0].message.content
        draft = json.loads(content)

        image_id, img_caption = get_and_upload_image(draft['image_kw'], wp)
        
        full_content = f"""
        <div style="background:#f0f7ff; padding:20px; border-left:5px solid #0056b3; margin-bottom:20px; border-radius:8px;">
            <strong>Quick Summary:</strong> {draft['excerpt']}
        </div>
        {draft['body']}
        <p style="font-size:0.8em; color:gray; margin-top:20px;">Featured Image: {img_caption}</p>
        <hr>
        <p><em>Reported by {Config.AUTHOR_NAME}, GCHAM Empire News.</em></p>
        """

        post = WordPressPost()
        post.title = draft['headline']
        post.content = full_content
        post.post_status = 'publish' 
        post.terms_names = {'category': ['Global News'], 'post_tag': ['GCHAM', '2026', 'Politics']}
        if image_id: post.thumbnail = image_id
        
        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM SUCCESS: Article {post_id} is live.")

    except Exception as e:
        logging.error(f"❌ Error: {e}")

if __name__ == "__main__":
    publish()
