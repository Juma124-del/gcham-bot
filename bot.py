import os, json, random, requests, logging, time
from datetime import datetime
from groq import Groq
from tavily import TavilyClient
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# ==========================================
# 🛡️ SECTION 1: CONFIG (GitHub Secrets)
# ==========================================
class Config:
    AUTHOR_NAME = "Brayan Juma Okumu"
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    
    GROQ_KEY = os.environ.get("GROQ_API_KEY")
    TAVILY_KEY = os.environ.get("TAVILY_API_KEY")
    PEXELS_KEY = os.environ.get("PEXELS_API_KEY")
    WP_URL = os.environ.get("WP_URL")  # https://gcham.com/xmlrpc.php
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
# 🌍 SECTION 3: THE GLOBAL SCOUT (Elite Update)
# ==========================================
def publish():
    logging.basicConfig(level=logging.INFO)
    try:
        tavily = TavilyClient(api_key=Config.TAVILY_KEY)
        groq = Groq(api_key=Config.GROQ_KEY)
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)

        # 🎯 PILLAR ROTATION & FLUID LENGTH
        category = random.choice(["Politics", "Economics", "Entertainment", "Sports"])
        target_words = random.randint(1200, 1600)
        
        logging.info(f"🌍 GCHAM Scouting {category} (USA, UK, France) | Target: {target_words} words...")
        
        # Scouting for "Direct Issues" in 1st world countries
        scout_query = f"breaking news {category} March 20 2026 USA UK France investigative details"
        scout = tavily.search(query=scout_query, search_depth="advanced")
        trends = "\n".join([f"- {r['title']}" for r in scout['results']])

        decision_msg = groq.chat.completions.create(
            messages=[{"role": "user", "content": f"Pick the #1 most hard-hitting 'Direct Issue' from: {trends}. Return ONLY the topic name."}],
            model="llama-3.3-70b-versatile"
        )
        decision = decision_msg.choices[0].message.content.strip()
        logging.info(f"🔥 Chosen Pillar Topic: {decision}")

        search = tavily.search(query=f"deep investigative reports, data, and power-player quotes for {decision}", search_depth="advanced")
        sources = "\n".join([f"Source: {r['url']}" for r in search['results'][:3]])
        context = "\n".join([r['content'] for r in search['results']])

        # 🚀 THE ELITE WRITER PROMPT
        writer_prompt = f"""
        Return ONLY a JSON object. Topic: {decision}. Context: {context}. 
        Sources: {sources}.
        Task: Write a {target_words}-word investigative report for GCHAM Empire.
        
        1. 'headline': A high-end, viral journalistic headline.
        2. 'excerpt': A 2-sentence SEO summary for the support box.
        3. 'body': The full report in HTML.
           - NO generic intros. Tackle the 'Direct Issue' immediately.
           - Use at least 6 H2/H3 subheadings to maintain 1200-1600 word depth.
           - Focus on impacts in Washington, London, and Paris.
           - Cite sources naturally using <a href='URL'>Source</a>.
        4. 'image_kw': SPECIFIC keyword (e.g., 'White House', 'London Stock Exchange', 'World Cup Stadium').
        5. 'wp_category': '{category}'
        """
        
        response = groq.chat.completions.create(
            messages=[{"role": "user", "content": writer_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            max_tokens=4000
        )
        
        draft = json.loads(response.choices[0].message.content)
        image_id, img_caption = get_and_upload_image(draft['image_kw'], wp)
        
        # 🛡️ THE PERSISTENT SUPPORT BOX (Brayan's Requirement)
        support_header = """
        <div style="background:#f0f7ff; border:2px solid #0056b3; padding:25px; border-radius:12px; margin-bottom:30px; font-family: sans-serif;">
            <h3 style="margin-top:0; color:#0056b3;">🛡️ GCHAM Empire: Independent Intelligence</h3>
            <p>Our global investigative reporting is reader-supported. We cover Politics, Economics, Entertainment, and Sports across the 1st world power centers.</p>
            <strong>Support Our Mission:</strong> <a href="mailto:gchamempire@gmail.com">gchamempire@gmail.com</a>
        </div>
        """
        
        full_content = f"""
        {support_header}
        <div style="background:#fffbe6; padding:15px; border:1px solid #ffe58f; margin-bottom:20px;">
            <strong>Editor's Summary:</strong> {draft['excerpt']}
        </div>
        {draft['body']}
        <p style="font-size:0.8em; color:gray; margin-top:20px;">Featured Image: {img_caption}</p>
        <hr>
        <p><em>Reported by {Config.AUTHOR_NAME}, Founder of GCHAM Empire.</em></p>
        """

        post = WordPressPost()
        post.title = draft['headline']
        post.content = full_content
        post.post_status = 'publish' 
        post.terms_names = {'category': [draft['wp_category']], 'post_tag': ['GCHAM', 'Global News', 'Investigative']}
        if image_id: post.thumbnail = image_id
        
        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM SUCCESS: {draft['wp_category']} article {post_id} is live.")

    except Exception as e:
        logging.error(f"❌ Error: {e}")

if __name__ == "__main__":
    publish()
