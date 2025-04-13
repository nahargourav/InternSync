from flask import Flask, render_template, request, redirect, url_for, session, flash,jsonify
import sqlite3
import hashlib
import os,subprocess,sys
import re
#import pyautogui
import WebScraper  # Import the WebScraper module to access the global variable
import requests
import openai
from dotenv import load_dotenv
load_dotenv()

# Set up Azure OpenAI API credentials
openai.api_type = "azure"
openai.api_base = "https://gourav-openai-service.openai.azure.com/"  # Replace with your Azure OpenAI endpoint
openai.api_version = "2023-05-15"  # Use the latest API version
openai.api_key =  os.getenv("OPENAI_API_KEY") # Replace with your API key

# Replace with your actual API key
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # Replace with your YouTube API key

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


# Initialize Flask application
app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Define the path to the Databases folder and database file
DATABASE_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Databases")
DATABASE_PATH = os.path.join(DATABASE_FOLDER, "internsync.db")

# Database connection function
def connect_db():
    try:
        # Ensure the Databases folder exists
        if not os.path.exists(DATABASE_FOLDER):
            os.makedirs(DATABASE_FOLDER)

        # Connect to the database
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row  # Allows fetching rows as dictionaries

        # Create the users table if it doesn't exist
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        conn.commit()

        # Create the ratings table if it doesn't exist
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                video_id TEXT NOT NULL,
                rating_type TEXT NOT NULL CHECK (rating_type IN ('like', 'dislike')),
                UNIQUE(user_id, video_id)  -- Ensure each user can rate a video only once
            )
        """)
        conn.commit()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS community_posts (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          user_id INTEGER,
                          course_name TEXT,
                          title TEXT,
                          description TEXT,
                          link TEXT,
                          timestamp TEXT DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS community_comments (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          post_id INTEGER,
                          user_id INTEGER,
                          comment TEXT,
                          timestamp TEXT DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

        # Add progress tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_name TEXT NOT NULL,
                video_id TEXT,
                project_id TEXT,
                completion_type TEXT CHECK (completion_type IN ('video', 'project')),
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, course_name, video_id, project_id)
            )
        """)
        conn.commit()

        print("✅ Database connected successfully!")
        return conn
    except sqlite3.Error as e:
        print(f"❌ Database connection error: {e}")
        return None

# Function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ------------------------- IMP TOPICS -------------------------

def get_top_industry_topics(subject):
    """Fetches the top 5 industry-relevant topics for placements in a given subject using ChatGPT."""
    
    prompt = f"""
    List exactly 5 most important topics in {subject} for industry and placements.
    Format: Return only the topic names, one per line, without numbers or bullets.
    Example:
    Topic One
    Topic Two
    Topic Three
    Topic Four
    Topic Five
    """

    try:
        response = openai.ChatCompletion.create(
            engine="gpt-4o-mini",  # Changed to correct engine name
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=100
        )

        # Split response into lines and clean up
        topics_text = response["choices"][0]["message"]["content"]
        topics_array = [topic.strip() for topic in topics_text.split('\n') if topic.strip()]
        
        # Ensure we have exactly 5 topics
        topics_array = topics_array[:5]
        
        return topics_array
    except Exception as e:
        print(f"Error: {str(e)}")
        return []

#Function to get resources
def search_youtube_videos(query, max_results=1):
    """Search for top YouTube videos related to the given query."""
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query + " tutorial",
        "maxResults": max_results,
        "type": "playlist",
        "key": YOUTUBE_API_KEY
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    playlists = []
    for item in data.get("items", []):
        playlist_title = item["snippet"]["title"]
        playlist_url = f"https://www.youtube.com/playlist?list={item['id']['playlistId']}"
        playlists.append((playlist_title, playlist_url))
    
    return playlists

# ------------------------- ROUTES -------------------------

# Home Page
@app.route('/')
def home():
    # Clear the session to flush any previous data
    session.clear()
    print("Session cleared.")  # Debugging
    return render_template('Home.html')

# List Internships Page
@app.route('/list_intern')
def list_intern():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = connect_db()
    jobs = conn.execute('SELECT role, company, link FROM courses').fetchall()
    conn.close()
    print("Fetched jobs:", jobs)  # Debugging
    return render_template('list_intern.html', courses=jobs)

@app.route("/search", methods=["POST"])
def search_internships():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Handle form data from POST request
    query = request.form.get("query", "").strip().lower()
    company = request.form.get("company", "").strip()
    location = request.form.get("location", "").strip() or "India"
    job_title = request.form.get("job_title", "").strip()

    # Debugging: Print received data
    print(f"Received data - Query: {query}, Company: {company}, Location: {location}, Job Title: {job_title}")

    # Store job_title in session
    session['job_title'] = job_title

    # Run the web scraper to get fresh results
    try:
        print(f"Running WebScraper with: company={company}, location={location}, job_title={job_title or query}")
        subprocess.run(["python", "WebScraper.py", company or query, location, job_title or query], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running WebScraper.py: {e}")

    # Redirect to the list_intern page to display results
    return redirect(url_for("list_intern"))

@app.route("/store_query", methods=["POST"])
def store_query():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "You must be logged in to perform this action."}), 401

    data = request.json
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"success": False, "message": "Invalid query data."}), 400

    session["query"] = query  # Store the query in the session
    print("Query stored in session:", query)  # Debugging
    return jsonify({"success": True, "message": "Query stored successfully."})

@app.route("/enroll", methods=["POST"])
def enroll():
    if "user_id" not in session:
        return jsonify({"message": "You must be logged in to enroll"}), 401

    user_id = session["user_id"]
    data = request.json
    query = data.get("query")  # Retrieve the query from the request body

    if not query:
        return jsonify({"message": "No query found. Please search first."}), 400

    print("Query retrieved for enrollment:", query)  # Debugging

    conn = connect_db()
    cursor = conn.cursor()
    skills = get_top_industry_topics(query)
    for skill in skills:
        print(f"Top YouTube videos for {skill}:")
        videos = search_youtube_videos(skill)
        for title, url in videos:
            print(f"- {title}: {url}")
            cursor.execute("""
                INSERT INTO resources (user_id, course_name, resource_title, resource_url) 
                VALUES (?, ?, ?, ?)
            """, (user_id, query, title, url))
            conn.commit()

    try:
        # Insert enrollment into the database
        cursor.execute("""
            INSERT INTO enrollments (user_id, course_name, enrollment_date) 
            VALUES (?, ?, DATE('now'))
        """, (user_id, query))
        conn.commit()
        return jsonify({"message": f"Successfully enrolled in {query}!"})
    except sqlite3.IntegrityError:
        return jsonify({"message": "Already enrolled in this internship!"}), 409
    finally:
        conn.close()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = hash_password(request.form["password"])  # Hash entered password

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE email = ? AND password = ?", (email, password))
        table = cursor.fetchone()
        conn.close()

        if table:
            session["user_id"] = table[0]
            session["username"] = table[1]
            flash("Login successful! Redirecting to dashboard...", "success")
            return redirect(url_for("Login_success"))
        else:
            #pyautogui.alert("Invlaid Credentials ", "Alert")
            flash("Invalid email or password!", "danger")
            return redirect(url_for("Login_failure"))

    return render_template("Login.html")

# ----------------- REGISTER FUNCTION -----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = hash_password(request.form["password"])

        conn = connect_db()
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                           (name, email, password))
            conn.commit()
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("User already exists!", "danger")
        finally:
            conn.close()

    return render_template("register.html")

# ----------------- DASHBOARD FUNCTION -----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please log in to access your dashboard.", "warning")
        return redirect(url_for("login"))

    return f"Welcome, {session['username']}! This is your dashboard."

# ----------------- LOGOUT FUNCTION -----------------
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

# ----------------- HOME LOGGED IN FUNCTION -----------------
@app.route("/home_logged_in")
def home_logged_in():
    return render_template("Home_logged_in.html")



# ----------------- LOGIN FAILURE FUNCTION -----------------
@app.route("/Login_failure")
def Login_failure():
    return render_template("Login_failure.html")

# ----------------- LOGIN SUCCESS FUNCTION -----------------
@app.route("/Login_success")
def Login_success():
    return render_template("Login_success.html")

# // ...existing code...

@app.route("/resources")
def resources():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    return render_template("resources.html")

# Keep only this version of get_enrolled_internships
@app.route("/get_enrolled_internships")
def get_enrolled_internships():
    if "user_id" not in session:
        return jsonify([])

    user_id = session["user_id"]
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        WITH 
        video_counts AS (
            SELECT course_name, COUNT(*) as total_videos
            FROM resources
            WHERE user_id = ?
            GROUP BY course_name
        ),
        progress AS (
            SELECT 
                course_name,
                COUNT(CASE WHEN completion_type = 'video' THEN 1 END) as completed_videos,
                COUNT(CASE WHEN completion_type = 'project' THEN 1 END) as completed_projects
            FROM user_progress
            WHERE user_id = ?
            GROUP BY course_name
        )
        SELECT 
            e.course_name, 
            e.enrollment_date,
            COALESCE(p.completed_videos, 0) as completed_videos,
            COALESCE(p.completed_projects, 0) as completed_projects,
            COALESCE(vc.total_videos, 0) as total_videos
        FROM enrollments e
        LEFT JOIN progress p ON e.course_name = p.course_name
        LEFT JOIN video_counts vc ON e.course_name = vc.course_name
        WHERE e.user_id = ?
    """, (user_id, user_id, user_id))

    internships = cursor.fetchall()
    conn.close()

    internships_list = []
    for internship in internships:
        internships_list.append({
            "course_name": internship[0],
            "date_posted": internship[1],
            "progress": {
                "videos": internship[2],
                "total_videos": internship[4],
                "projects": internship[3],
                "total_projects": 3  # Fixed number of projects per course
            }
        })

    return jsonify(internships_list)


# VIDEOS

@app.route("/videos")
def videos():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    return render_template("videos.html")

@app.route("/get_enrolled_videos")
def get_enrolled_videos():
    if "user_id" not in session:
        return jsonify([])  # Return empty list if user is not logged in

    user_id = session["user_id"]
    course_name = request.args.get("course_name", "").strip()  # Retrieve course_name from query parameters

    print(f"Received course_name: {course_name}")  # Debugging: Log the course_name

    if not course_name:
        print("Error: course_name is missing or empty")  # Debugging: Log the error
        return jsonify({"message": "Course name is required"}), 400

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT resources.resource_title, resources.resource_url
        FROM resources
        WHERE resources.user_id = ? AND resources.course_name = ?
    """, (user_id, course_name))

    resources = cursor.fetchall()
    print(f"Fetched resources: {resources}")  # Debugging: Log the fetched resources
    conn.close()

    resources_list = []
    for resource in resources:
        resources_list.append({
            "resource_name": resource[0],
            "resource_url": resource[1],
        })

    return jsonify(resources_list)

# // ...existing code...

# Route to handle video ratings
@app.route("/rate_video", methods=["POST"])
def rate_video():
    if "user_id" not in session:
        return jsonify({"message": "You must be logged in to rate videos"}), 401

    user_id = session["user_id"]
    data = request.json
    video_id = data.get("video_id")
    rating_type = data.get("rating_type")

    if not video_id or rating_type not in ["like", "dislike"]:
        return jsonify({"message": "Invalid data"}), 400

    conn = connect_db()
    cursor = conn.cursor()

    try:
        # Insert or update the rating
        cursor.execute("""
            INSERT INTO ratings (user_id, video_id, rating_type)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, video_id) DO UPDATE SET rating_type = excluded.rating_type
        """, (user_id, video_id, rating_type))
        conn.commit()
        return jsonify({"message": "Rating submitted successfully!"})
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({"message": "An error occurred"}), 500
    finally:
        conn.close()

# Route to fetch video ratings
@app.route("/get_video_ratings", methods=["GET"])
def get_video_ratings():
    video_id = request.args.get("video_id")

    if not video_id:
        return jsonify({"message": "Video ID is required"}), 400

    conn = connect_db()
    cursor = conn.cursor()

    try:
        # Fetch the total likes and dislikes for the video
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN rating_type = 'like' THEN 1 ELSE 0 END) AS likes,
                SUM(CASE WHEN rating_type = 'dislike' THEN 1 ELSE 0 END) AS dislikes
            FROM ratings
            WHERE video_id = ?
        """, (video_id,))
        result = cursor.fetchone()
        return jsonify({"likes": result["likes"] or 0, "dislikes": result["dislikes"] or 0})
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({"message": "An error occurred"}), 500
    finally:
        conn.close()

#--------------------PROJECTS------------------


def get_projects_for_company(company_name):
    """Generate project ideas for a given company using Azure OpenAI."""
    prompt = f"""Generate 3 project ideas for {company_name} internship in this exact format:

### Project 1: **[Project Name]**

#### Problem Statement:
[Problem description]

#### Tech Stack:
- **Languages**: [languages]
- **Frameworks**: [frameworks]
- **Libraries**: [libraries]
- **Database**: [database]
- **Frontend**: [frontend]

#### Unique Features:
- [Feature 1]
- [Feature 2]
- [Feature 3]
- [Feature 4]

---

[Repeat format for Projects 2 and 3]
"""

    response = openai.ChatCompletion.create(
        engine="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1000  # Increased max_tokens for longer response
    )

    return response["choices"][0]["message"]["content"]

# PROJECTS

@app.route("/projects")
def projects():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    return render_template("projects.html")

@app.route("/get_projects")
def get_projects():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    course_name = request.args.get("course_name", "").strip()
    print(f"Received course name in get_projects: {course_name}")  # Debug log

    if not course_name:
        return jsonify({"error": "Course name required"}), 400

    try:
        print(f"Calling get_projects_for_company with: {course_name}")  # Debug log
        projects = get_projects_for_company(course_name)
        print(f"Generated projects response: {projects}")  # Debug log
        return jsonify({"projects": projects})
    except Exception as e:
        print(f"Error generating projects: {e}")
        return jsonify({"error": str(e)}), 500

#--------------------community------------------

# Route to add a post
@app.route('/add_post', methods=['POST'])
def add_post():
    data = request.json
    user_id = data['user_id']
    course_name = data['course_name']
    title = data['title']
    description = data['description']
    link = data.get('link', '')
    
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO community_posts (user_id, course_name, title, description, link) VALUES (?, ?, ?, ?, ?)",
                       (user_id, course_name, title, description, link))
        conn.commit()
    
    return jsonify({'message': 'Post added successfully'}), 201

# Route to fetch posts for a course
@app.route('/get_posts/<course_name>', methods=['GET'])
def get_posts(course_name):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.user_id, p.course_name, p.title, p.description, p.link, p.timestamp, u.username
            FROM community_posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.course_name = ?
            ORDER BY p.timestamp DESC
        """, (course_name,))
        posts = cursor.fetchall()
    
    return jsonify([{
        'id': post[0], 'user_id': post[1], 'course_name': post[2], 'title': post[3],
        'description': post[4], 'link': post[5], 'timestamp': post[6], 'username': post[7]
    } for post in posts])

@app.route('/get_comments/<int:post_id>', methods=['GET'])
def get_comments(post_id):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.post_id, c.user_id, c.comment, c.timestamp, u.username
            FROM community_comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.post_id = ?
            ORDER BY c.timestamp ASC
        """, (post_id,))
        comments = cursor.fetchall()
    
    return jsonify([{
        'id': comment[0], 'post_id': comment[1], 'user_id': comment[2],
        'comment': comment[3], 'timestamp': comment[4], 'username': comment[5]
    } for comment in comments])

#--------------------ChatBOt------------------

def markdown_to_html(text):
    """Convert Markdown-style text (bold, italic, code) to HTML for chatbot responses."""
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)  # Bold (**text**)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)  # Italic (*text*)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)  # Inline code (`code`)
    text = text.replace("\n", "<br>")  # New line handling
    return text


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

# Add new route to mark item as completed
@app.route("/mark_completed", methods=["POST"])
def mark_completed():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.json
    user_id = session["user_id"]
    course_name = data.get("course_name")
    item_id = data.get("item_id")
    completion_type = data.get("type")  # 'video' or 'project'
    
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        if completion_type == "video":
            cursor.execute("""
                INSERT INTO user_progress (user_id, course_name, video_id, completion_type)
                VALUES (?, ?, ?, 'video')
            """, (user_id, course_name, item_id))
        else:
            cursor.execute("""
                INSERT INTO user_progress (user_id, course_name, project_id, completion_type)
                VALUES (?, ?, ?, 'project')
            """, (user_id, course_name, item_id))
        conn.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"message": "Already marked as completed"}), 409
    finally:
        conn.close()


@app.route("/check_completion")
def check_completion():
    if "user_id" not in session:
        return jsonify({"completed": False}), 401

    user_id = session["user_id"]
    item_id = request.args.get("item_id")
    course_name = request.args.get("course_name")
    completion_type = request.args.get("type")

    if not all([item_id, course_name, completion_type]):
        return jsonify({"completed": False, "error": "Missing parameters"}), 400

    conn = connect_db()
    cursor = conn.cursor()

    try:
        if completion_type == "video":
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM user_progress 
                    WHERE user_id = ? 
                    AND course_name = ? 
                    AND video_id = ? 
                    AND completion_type = 'video'
                )
            """, (user_id, course_name, item_id))
        else:
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM user_progress 
                    WHERE user_id = ? 
                    AND course_name = ? 
                    AND project_id = ? 
                    AND completion_type = 'project'
                )
            """, (user_id, course_name, item_id))

        result = cursor.fetchone()[0] == 1
        return jsonify({"completed": result})
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"completed": False, "error": str(e)}), 500
    finally:
        conn.close()

# ...existing code...

@app.route("/community")
def community():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    course_name = request.args.get("course_name", "")
    return render_template("community.html", course_name=course_name)

# ...existing code...

@app.route("/search_from_hero", methods=["POST"])
def search_from_hero():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Handle form data from POST request
    query = request.form.get("query", "").strip().lower()

    # Debugging: Print received data
    print(f"Received data from Hero.html - Query: {query}")

    # Store the query in the session
    session["query"] = query
    print(f"Query stored in session: {session['query']}")  # Debugging

    # Run the web scraper to get fresh results
    try:
        print(f"Running WebScraper with query: {query}")
        subprocess.run(["python", "WebScraper.py", query, "India", query], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running WebScraper.py: {e}")
        flash("An error occurred while fetching internships. Please try again.", "danger")
        return redirect(url_for("list_intern"))

    # Fetch the scraped results from the database
    conn = connect_db()
    jobs = conn.execute('SELECT role, company, link FROM courses').fetchall()
    conn.close()

    # Redirect to list_intern.html with the results
    return render_template('list_intern.html', courses=jobs, from_hero=True)

if __name__ == '__main__':
    app.run(debug=True)