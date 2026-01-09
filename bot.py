import os
import re
import random
import json
import httplib2
import requests
from groq import Groq
from oauth2client.service_account import ServiceAccountCredentials
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from wordpress_xmlrpc.compat import xmlrpc_client
from slugify import slugify

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GEMINI_API_KEY") 
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")
INDEX_JSON = os.getenv("INDEXING_SERVICE_JSON")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

client = Groq(api_key=GROQ_API_KEY)
wp_client = Client(WP_URL, WP_USER, WP_PASS)

def get_wikimedia_image(search_term):
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"File:{search_term}", "gsrlimit": 1,
        "prop": "imageinfo", "iiprop": "url|user"
    }
    try:
        response = requests.get(url, params=params).json()
        pages = response.get("query", {}).get("pages", {})
        for pgid, data in pages.items():
            info = data["imageinfo"][0]
            return info["url"], info.get("user", "Wikimedia")
    except: return None, None

def get_free_image(topic):
    # Try Wikimedia first for "Real Faces" (Celebrities/Figures)
    img_url, author = get_wikimedia_image(topic.split()[0])
    
    # Fallback to Pexels for high-quality thematic photos
    if not img_url and PEXELS_KEY:
        try:
            headers = {"Authorization": PEXELS_KEY}
            url = f"https://api.pexels.com/v1/search?query={topic}&per_page=1"
            res = requests.get(url, headers=headers).json()
            if res.get('photos'):
                img_url = res['photos'][0]['src']['large']
                author = res['photos'][0]['photographer']
        except: pass
    return img_url, author

def upload_to_wp(img_url, title):
    try:
        response = requests.get(img_url)
        filename = f"{slugify(title)}.jpg"
        data = {'name': filename, 'type': 'image/jpeg', 'bits': xmlrpc_client.Binary(response.content)}
        res = wp_client.call(media.UploadFile(data))
        return res['id'], res['url']
    except: return None, None

def generate_viral_content(topic):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"""
    Write a VIRAL and ETHICAL news report for a USA audience about '{topic}'.
    
    STRUCTURE (INVERTED PYRAMID STYLE):
    1. THE LEAD: Start with a 2-sentence 'ICYMI' summary in a <blockquote>. The first paragraph MUST cover the 'Who, What, Where, When, and Why'.
    2. THE BODY: Provide supporting evidence, details, and an 'Impact & Public Reaction' section.
    3. THE TAIL: Include a 'People Also Ask: FAQ' (3 questions using <h3>) and a final 'GCHAM Global News Desk Analysis'.
    
    JOURNALISTIC STANDARDS:
    - Maintain strict objectivity, fairness, and neutrality.
    - Attribute claims to 'reports' or 'sources'.
    - Use 'Click-worthy' but 'Truth-bound' headers. 1,200 words.
    
    FORMAT: Clean HTML only. Link to <a href='{base_url}'>GCHAM News</a>.
    """
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.7
    )
    return completion.choices[0].message.content

def notify_google_indexing(url):
    try:
        if not INDEX_JSON: return
        key_data = json.loads(INDEX_JSON)
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(key_data, ["https://www.googleapis.com/auth/indexing"])
        http = credentials.authorize(httplib2.Http())
        data = json.dumps({"url": url, "type": "URL_UPDATED"})
        http.request("https://indexing.googleapis.com/v3/urlNotifications:publish", method="POST", body=data)
        print("✅ Google Indexing Notified!")
    except Exception as e: print(f"❌ Indexing Error: {e}")

def publish():
    print("🚀 GCHAM: Executing News Desk Protocol...")
    niches = ["US Economy", "Silicon Valley Tech", "USA Politics", "Premier League", "Hollywood & Entertainment"]
    niche = random.choice(niches)
    
    topic_call = client.chat.completions.create(
        messages=[{"role": "user", "content": f"One trending USA news headline for {niche}. Just the title."}],
        model="llama-3.3-70b-versatile"
    )
    topic = topic_call.choices[0].message.content.strip().replace('"', '')

    content = generate_viral_content(topic)
    img_url, author = get_free_image(topic)
    img_id, final_img_url = upload_to_wp(img_url, topic) if img_url else (None, None)

    post = WordPressPost()
    post.title = topic
    if final_img_url:
        img_html = f'<figure><img src="{final_img_url}" alt="{topic}" style="width:100%;"/><figcaption>Credit: {author}</figcaption></figure>'
        content = content.replace('</h1>', f'</h1>{img_html}') # Inserts image after title tag
        post.thumbnail = img_id

    post.content = content
    post.post_status = 'publish'
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', 'Journalism', 'Trending']}
    
    try:
        post_id = wp_client.call(posts.NewPost(post))
        final_post = wp_client.call(posts.GetPost(post_id))
        print(f"✅ SUCCESS! Live at: {final_post.link}")
        notify_google_indexing(final_post.link)
    except Exception as e: print(f"❌ Error: {e}")

if __name__ == "__main__":
    publish()
