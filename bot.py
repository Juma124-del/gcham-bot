import os, json, re, random, requests, logging, time
from datetime import datetime
from groq import Groq
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client

# --- 1. SYSTEM CONFIG ---
SYSTEM_VERSION = "GCHAM Final Shield v4.2"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pexels_image(query):
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key: return None, None
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get('photos'):
                photo_url = data['photos'][0]['src']['large']
                img_res = requests.get(photo_url, timeout=10)
                return img_res.content, "image/jpeg"
    except Exception as e:
        logging.warning(f"⚠️ Image skip: {e}")
    return None, None

def clean_for_xml(text):
    """Remove characters that crash the WordPress XML-RPC parser"""
    if not text: return ""
    return "".join(c for c in text if c.isprintable()).encode('utf-8', 'ignore').decode('utf-8')

def publish():
    # --- 2. ENVIRONMENT CHECK ---
    groq_api_key = os.getenv("GROQ_API_KEY")
    wp_url = os.getenv("WP_URL")
    wp_user = os.getenv("WP_USER")
    wp_pass = os.getenv("WP_PASS")

    if not all([groq_api_key, wp_url, wp_user, wp_pass]):
        logging.error("❌ Missing Env Variables. Check your Secret Variables / Platform Secrets.")
        return

    NICHE_PROFILES = {
        "USA Politics": "draft",
        "Economics": "draft",
        "Sports": "publish",
        "Crypto": "publish",
        "Entertainment": "publish"
    }
    niche = random.choice(list(NICHE_PROFILES.keys()))
    
    # --- 3. THE REFINED "SENIOR EDITOR" PROMPT ---
    system_message = (
        "You are the Senior Editor for GCHAM News, a premier USA digital outlet. "
        "Your style is authoritative and SEO-optimized. Every article MUST be at least 800 words. "
        "Force professional HTML structure: Use exactly one <h1> for the headline, "
        "multiple <h2> and <h3> for sections, and <ul> for key takeaways. "
        "Current date: January 11, 2026. Focus on real-time data and specific names."
    )

    user_message = (
        f"Generate a professional news report on {niche} for January 11, 2026. "
        f"Include historical context and 2026 projections. "
        f"Return ONLY a raw JSON object: "
        '{"headline": "", "body_html": "", "img_keyword": ""}'
    )

    client = Groq(api_key=groq_api_key)
    
    try:
        # Generation with JSON Response Format
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        data = json.loads(res.choices[0].message.content)

        # --- 4. WORDPRESS CONNECTION ---
        wp = Client(wp_url, wp_user, wp_pass)
        
        # Image Handling
        img_bits, img_type = get_pexels_image(data.get('img_keyword', niche))
        f_id = None
        if img_bits:
            try:
                u_res = wp.call(media.UploadFile({
                    'name': f"g_{int(time.time())}.jpg", 
                    'type': img_type, 
                    'bits': xmlrpc_client.Binary(img_bits)
                }))
                f_id = u_res.get('id')
            except: logging.warning("⚠️ Image upload failed, continuing with text only.")

        # --- 5. CLEANING & DEPLOYMENT ---
        post = WordPressPost()
        post.title = clean_for_xml(data.get('headline', 'GCHAM News Update'))
        
        # Adding the Signature & Professional Formatting
        header_sig = f"<p><em>Reported by <strong>Brayan Juma</strong> — Editor</em></p><hr>"
        post.content = header_sig + clean_for_xml(data.get('body_html', ''))
        
        post.post_status = NICHE_PROFILES[niche]
        if f_id: post.thumbnail = f_id

        wp.call(posts.NewPost(post))
        logging.info(f"✅ SUCCESS: {post.title} (Status: {post.post_status})")

    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR: {e}")

if __name__ == "__main__":
    publish()
