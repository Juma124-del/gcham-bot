import os, json, re, random, requests, logging, time, socket
from datetime import datetime
from groq import Groq
from tavily import TavilyClient  
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods import posts, media
from oauth2client.service_account import ServiceAccountCredentials
import httplib2

# ==========================================================
# 🛡️ SECTION 1: CONFIG
# ==========================================================
class Config:
    VERSION = "GCHAM Empire Shield v6.6"
    CURRENT_DATE = datetime.now().strftime("%B %d, %Y")
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_KEY = os.getenv("TAVILY_API_KEY")
    WP_URL = os.getenv("WP_URL")
    WP_USER = os.getenv("WP_USER")
    WP_PASS = os.getenv("WP_PASS")
    BING_KEY = os.getenv("BING_API_KEY")
    DOMAIN = "gcham.com"
    INDEXING_FOLDER = "INDEXING_SERVICE_JSON"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================================
# 🧠 SECTION 2: FACT GATHERING (Safely handling lists)
# ==========================================================

def get_live_context(niche):
    tavily = TavilyClient(api_key=Config.TAVILY_KEY)
    query = f"Latest {niche} news USA {Config.CURRENT_DATE} investigative"
    try:
        search_result = tavily.search(query=query, topic="news", days=1, max_results=8)
        fact_list = []
        for res in search_result['results']:
            fact_list.append(f"SOURCE: {res['title']}\nFACT: {res['content']}\n")
        
        # 🛡️ FIX: Safely join the list into one big string
        return "\n".join(fact_list) 
    except Exception as e:
        return f"Focus on {Config.CURRENT_DATE} industry developments."

# ==========================================================
# ✍️ SECTION 3: THE EDITOR (800-1500 Words + Anti-Hallucination)
# ==========================================================

def publish():
    niche = random.choice(["USA Politics", "Economics", "Sports", "Crypto", "Entertainment"])
    live_facts = get_live_context(niche)
    
    client = Groq(api_key=Config.GROQ_KEY)
    
    # Updated Prompt: Specific word count and strict factual instructions
    system_message = (
        f"You are the Lead Investigative Journalist at GCHAM. Today is {Config.CURRENT_DATE}. "
        "Write an 800-1500 word factual report for a USA audience. "
        "INSTRUCTIONS: "
        "1. Start with a 'google_snippet' field (150 chars). "
        "2. Provide 'full_report' with H1, H2, H3 tags in HTML. "
        "3. Expand every fact by explaining its economic or social impact on the USA. "
        "4. STRICT: If you run out of facts, analyze the long-term trends of the topic. DO NOT HALLUCINATE."
        "Format: JSON ONLY."
    )

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_message}, 
                {"role": "user", "content": f"Live Facts: {live_facts}"}
            ],
            temperature=0.4, # Low creativity for high accuracy
            response_format={"type": "json_object"}
        )
        data = json.loads(completion.choices[0].message.content)
        
        # 🛡️ FIX: Ensure fields are strings, even if AI accidentally sends a list
        report_text = data.get('full_report', '')
        if isinstance(report_text, list):
            report_text = " ".join(report_text)
            
        snippet_text = data.get('google_snippet', '')
        if isinstance(snippet_text, list):
            snippet_text = " ".join(snippet_text)

        # Build Final Content
        styled_snippet = (
            f"<div style='background:#f4f4f4; padding:20px; border-left:5px solid #cc0000; margin-bottom:20px;'>"
            f"<strong>GCHAM INSIGHT:</strong> {snippet_text}</div>"
        )
        final_content = styled_snippet + report_text

        # WordPress Push
        wp = Client(Config.WP_URL, Config.WP_USER, Config.WP_PASS)
        post = WordPressPost()
        post.title = data.get('headline', f"{niche} Intelligence Report - {Config.CURRENT_DATE}")
        post.content = final_content
        post.post_status = 'publish'
        
        post_id = wp.call(posts.NewPost(post))
        logging.info(f"✅ GCHAM SUCCESS: Post {post_id} Published.")

    except Exception as e:
        logging.error(f"❌ Execution Error: {e}")

if __name__ == "__main__":
    publish()
