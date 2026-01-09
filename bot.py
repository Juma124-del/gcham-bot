import json
import httplib2
from oauth2client.service_account import ServiceAccountCredentials

# This function uses the Secret you just added to GitHub
def notify_google_indexing(url):
    print(f"📡 Pinging Google Indexing API for: {url}")
    try:
        # Load the JSON from your GitHub Secret
        json_key = os.getenv("INDEXING_SERVICE_JSON")
        if not json_key:
            print("⚠️ No Indexing JSON found. Skipping Google ping.")
            return

        scopes = ["https://www.googleapis.com/auth/indexing"]
        key_data = json.loads(json_key)
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(key_data, scopes=scopes)
        
        http = credentials.authorize(httplib2.Http())
        endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
        
        # Notify Google that a new URL was updated/created
        data = json.dumps({"url": url, "type": "URL_UPDATED"})
        response, content = http.request(endpoint, method="POST", body=data)
        
        if response.status == 200:
            print("✅ Google notified! Your article is now in the priority crawl queue.")
        else:
            print(f"⚠️ Indexing API responded with status: {response.status}")
    except Exception as e:
        print(f"❌ Indexing Error: {e}")

# This replaces your old publish function
def publish():
    print("🚀 GCHAM: Launching Groq Engine...")
    topic, niche = get_trending_usa_topic()
    if not topic: return

    content = generate_article(topic, niche)
    
    post = WordPressPost()
    post.title = topic # Or extract from H1
    post.content = content
    post.post_status = 'publish'
    
    try:
        # 1. Publish to WordPress
        post_id = wp_client.call(posts.NewPost(post))
        final_post = wp_client.call(posts.GetPost(post_id))
        article_url = final_post.link
        print(f"✅ Article Live: {article_url}")
        
        # 2. Automatically Index on Google
        notify_google_indexing(article_url)
        
    except Exception as e:
        print(f"❌ WordPress Error: {e}")
