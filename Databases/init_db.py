import sqlite3

def create_database():
    # Connect to SQLite database (Creates 'internsync.db' if it doesn't exist)
    conn = sqlite3.connect("internsync.db")
    cursor = conn.cursor()

    # Enable Foreign Key Constraints
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Create Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    );
    """)

    # Create Courses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        company TEXT NOT NULL,
        link TEXT UNIQUE NOT NULL,
        date_posted TEXT NOT NULL
    );
    """)

    # Create Enrollments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        course_id INTEGER,
        course_name TEXT NOT NULL,
        enrollment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    # Create Resources Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        course_name TEXT NOT NULL,
        resource_title TEXT NOT NULL,
        resource_url TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (course_name) REFERENCES enrollments(course_name) ON DELETE CASCADE
    );
    """)

    # Commit and close the connection
    conn.commit()
    conn.close()

    print("InternSync Database created successfully!")

# Run the function to create the database
if __name__ == "__main__":
    create_database()
