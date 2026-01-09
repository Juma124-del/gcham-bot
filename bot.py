import os
import re
import random
import json
import httplib2
from groq import Groq
from oauth2client.service_account import ServiceAccountCredentials
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GEMINI_API_KEY") 
WP_URL = os.getenv("WP_URL")
WP_USER = os.getenv("WP_USER")
WP_PASS = os.getenv("WP_PASS")
INDEX_JSON = os.getenv("INDEXING_SERVICE_JSON")

# Initialize Clients
client = Groq(api_key=GROQ_API_KEY)
wp_client = Client(WP_URL, WP_USER, WP_PASS)

def notify_google_indexing(url):
    print(f"📡 Pinging Google Indexing API for: {url}")
    try:
        if not INDEX_JSON:
            print("⚠️ No Indexing JSON found. Skipping.")
            return
        scopes = ["https://www.googleapis.com/auth/indexing"]
        key_data = json.loads(INDEX_JSON)
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(key_data, scopes=scopes)
        http = credentials.authorize(httplib2.Http())
        endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
        data = json.dumps({"url": url, "type": "URL_UPDATED"})
        response, content = http.request(endpoint, method="POST", body=data)
        if response.status == 200:
            print("✅ Google notified successfully!")
    except Exception as e:
        print(f"❌ Indexing Error: {e}")

def get_trending_topic():
    niches = ["US Economy", "Silicon Valley Tech", "USA Politics", "American Lifestyle"]
    selected = random.choice(niches)
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": f"One trending USA news headline for {selected}. Headline only."}],
            model="llama-3.3-70b-versatile",
        )
        return completion.choices[0].message.content.strip(), selected
    except: return None, None

def generate_article(topic):
    base_url = WP_URL.replace('/xmlrpc.php', '')
    prompt = f"Write a 1200-word news report on '{topic}'. Use <h1> for title and <h2> for subheaders. Professional style. Link to <a href='{base_url}'>GCHAM News</a>. Use clean HTML."
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
    )
    return completion.choices[0].message.content

def publish():
    print("🚀 GCHAM: Starting Groq + Google Indexing...")
    topic, niche = get_trending_topic()
    if not topic: return
    
    content = generate_article(topic)
    title_match = re.search('<h1>(.*?)</h1>', content)
    final_title = title_match.group(1) if title_match else topic

    post = WordPressPost()
    post.title = final_title
    post.content = content
    post.post_status = 'publish'
    post.terms_names = {'category': [niche], 'post_tag': ['USA News', 'Groq']}
    
    try:
        post_id = wp_client.call(posts.NewPost(post))
        final_post = wp_client.call(posts.GetPost(post_id))
        print(f"✅ Live at: {final_post.link}")
        notify_google_indexing(final_post.link)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    publish()
