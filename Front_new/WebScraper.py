import sqlite3
import sys
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Set database path
DATABASE_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Databases")
DB_PATH = os.path.join(DATABASE_FOLDER, "internsync.db")

def create_database():
    """Create the database and jobs table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            company TEXT NOT NULL,
            link TEXT UNIQUE NOT NULL,
            date_posted TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def clear_database():
    """Flush old job listings before storing new ones."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM courses")  # Clear old data
    conn.commit()
    conn.close()

def store_job(role, company, link, date_posted):
    """Store the job details in the database, avoiding duplicates."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO courses (role, company, link) 
        VALUES (?, ?, ?)
    """, (role, company, link))
    conn.commit()
    conn.close()

def scrape_jobs(company="", location="India", job_title=""):
    """Scrape LinkedIn job postings quickly (1-2 pages)."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")  # Prevent bot detection
    options.add_argument("--disable-dev-shm-usage")  # Reduce crashes in headless mode
    options.add_argument("--disable-extensions")  # Prevent extension issues
    options.add_argument("start-maximized")
    
    # Use a mobile user-agent (optional, sometimes bypasses bot detection)
    options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    if not os.environ.get('APPEND_RESULTS', False):
        clear_database()

    # Define the search query
    keywords = "intern OR internship OR internships"
    if job_title:
        keywords = f"{job_title} ({keywords})"
    if company:
        keywords = f"{company} ({keywords})"
    
    base_url = "https://www.linkedin.com/jobs/search"
    total_jobs_found = 0
    max_pages = 2  # **Set to 1-2 pages for faster scraping**

    # Updated CSS Selectors for LinkedIn
    JOB_CARD = ".job-search-card"
    JOB_TITLE = ".base-search-card__title"
    COMPANY_NAME = ".base-search-card__subtitle"
    JOB_LINK = "a.base-card__full-link"
    DATE_POSTED = ".job-search-card__listdate"

    try:
        for page in range(max_pages):
            search_url = f"{base_url}?keywords={keywords}&location={location}&start={page*25}"
            print(f"\U0001F30D Fetching: {search_url}")
            driver.get(search_url)

            try:
                # Wait for job listings to load (reduced timeout to 6s)
                WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CSS_SELECTOR, JOB_CARD)))

                jobs = driver.find_elements(By.CSS_SELECTOR, JOB_CARD)
                print(f"Page {page+1}: Found {len(jobs)} job cards.")

                if not jobs:
                    print(f"No more jobs found on page {page+1}, stopping pagination.")
                    break

                for job in jobs:
                    try:
                        role = job.find_element(By.CSS_SELECTOR, JOB_TITLE).text.strip()
                        company_name = job.find_element(By.CSS_SELECTOR, COMPANY_NAME).text.strip()
                        link = job.find_element(By.CSS_SELECTOR, JOB_LINK).get_attribute("href")

                        # Handle Date Posted
                        date_posted = "Unknown"
                        try:
                            date_elem = job.find_element(By.CSS_SELECTOR, DATE_POSTED)
                            date_posted = date_elem.text.strip()
                        except Exception:
                            pass  # If date is missing, keep "Unknown"

                        # Ensure only internship roles are stored
                        if any(word in role.lower() for word in ["intern", "internship", "internships"]):
                            store_job(role, company_name, link, date_posted)
                            total_jobs_found += 1
                            print(f"✅ Stored: {role} at {company_name}")
                    except Exception as e:
                        print(f"⚠️ Error processing job card: {e}")

            except Exception as e:
                print(f"⚠️ Error loading jobs on page {page+1}: {e}")
                break

    except Exception as e:
        print(f"❌ Error in scraping process: {e}")
    finally:
        driver.quit()

    print(f"✅ Scraping complete. Total jobs stored: {total_jobs_found}")
    return total_jobs_found

if __name__ == "__main__":
    create_database()
    company = sys.argv[1] if len(sys.argv) > 1 else ""
    location = sys.argv[2] if len(sys.argv) > 2 else "India"
    job_title = sys.argv[3] if len(sys.argv) > 3 else ""

    scrape_jobs(company, location, job_title)
