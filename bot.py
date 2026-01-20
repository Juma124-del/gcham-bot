import os, json, re, random, requests, logging, time, socket
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client # Added for media upload
from oauth2client.service_account import ServiceAccountCredentials
import httplib2

# ==========================================
# 🛡️ SECTION 1: CONFIG
# ==========================================
class Config:
    VERSION = "GCHAM Empire Shield v6.7"
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    PEXELS_KEY = os.getenv("PEXELS_API_KEY") # 📸 REQUIRED FOR IMAGES
    WP_URL = os.getenv("WP_URL")
    WP_USER = os.getenv("WP_USER")
    WP_PASS = os.getenv("WP_PASS")

# ==========================================
# 📸 SECTION 2: IMAGE LOGIC (The Fix)
# ==========================================

def get_and_upload_image(keyword, wp_client):
    """Searches Pexels and uploads to WP Media Library"""
    if not Config.PEXELS_KEY: return None
    
    headers = {"Authorization": Config.PEXELS_KEY}
    url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=1"
    
    try:
        res = requests.get(url, headers=headers).json()
        if not res.get('photos'): return None
        
        img_url = res['photos'][0]['src']['large']
        img_data = requests.get(img_url).content
        filename = f"gcham_{int(time.time())}.jpg"
        
        # Prepare for WordPress Upload
        data = {
            'name': filename,
            'type': 'image/jpeg',
            'bits': xmlrpc_client.Binary(img_data),
            'overwrite': True
        }
        
        upload = wp_client.call(media.UploadFile(data))
        return upload.get('id') # Returns ID for Featured Image
    except Exception as e:
        logging.error(f"❌ Image Error: {e}")
        return None

# ==========================================
# ✍️ SECTION 3: PUBLISHING
# ==========================================

def publish():
    niche = random.choice(["USA Politics", "Economics", "Sports", "Crypto", "Entertainment"])
    # ... [Same context/Groq logic as v6.6] ...
    
    try:
        # 1. Connect to WordPress
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)
        
        # 2. Get Featured Image using AI-generated keywords
        image_id = get_and_upload_image(data.get('image_kw', niche), wp)
        
        # 3. Assemble Post
        post = WordPressPost()
        post.title = data.get('headline')
        post.content = final_content # Excerpt + Full Body
        post.post_status = 'publish'
        
        if image_id:
            post.thumbnail = image_id # ✅ Sets the Featured Image
            
        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM SUCCESS: Post {post_id} with Image {image_id}")

    except Exception as e:
        logging.error(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    publish()
