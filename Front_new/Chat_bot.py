import re
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__, template_folder="templates")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

def markdown_to_html(text):
    """Convert Markdown-style text (bold, italic, code) to HTML for chatbot responses."""
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)  # Bold (**text**)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)  # Italic (*text*)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)  # Inline code (`code`)
    text = text.replace("\n", "<br>")  # New line handling
    return text

# @app.route("/")
# def index():
#     return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_input = data.get("message", "")

    if not user_input:
        return jsonify({"response": "Please enter a message."})

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": user_input}]
    }

    try:
        response = requests.post(GROQ_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()

        bot_reply = response.json()["choices"][0]["message"]["content"]

        # Convert Markdown-style text to HTML
        bot_reply = markdown_to_html(bot_reply)

        return jsonify({"response": bot_reply})

    except requests.exceptions.RequestException as e:
        print("Groq API Error:", str(e))
        return jsonify({"response": f"API Error: {str(e)}"})

if __name__ == "__main__":
    app.run(debug=True)
