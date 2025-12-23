from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import pandas as pd
import time
import os
from dotenv import load_dotenv
from query_variations import query_variations

def collect_linkedin_data(query="Sheikh Tamim ibn Hamad Al Thani", max_posts=20, max_comments=5, output_file="linkedin_data.csv"):
    load_dotenv()
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if not email or not password:
        raise ValueError("LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set in .env")

    options = Options()
    options.headless = False  # Set to True after testing
    driver = webdriver.Chrome(options=options)
    try:
        # Login to LinkedIn
        driver.get("https://www.linkedin.com/login")
        time.sleep(3)
        driver.find_element(By.ID, "username").send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password + Keys.RETURN)
        time.sleep(3)  # Wait for login

        # Search and scrape
        url = f"https://www.linkedin.com/search/results/content/?keywords={query}"
        driver.get(url)
        print(f"Scraping LinkedIn for '{query}'...")

        post_data = []
        scrolls = 0
        while len(post_data) < max_posts and scrolls < 10:
            posts = driver.find_elements(By.CSS_SELECTOR, "div.feed-shared-update-v2")
            for post in posts[:max_posts - len(post_data)]:
                try:
                    text = post.find_element(By.CSS_SELECTOR, "span.break-words").text or "unknown"
                    date = post.find_element(By.CSS_SELECTOR, "time").get_attribute("datetime") or "unknown"
                    likes = (post.find_element(By.CSS_SELECTOR, "span.social-details-social-counts__reactions-count").text 
                             or "unknown")
                    post_link = post.find_element(By.XPATH, ".//ancestor::div[contains(@class, 'feed-shared-update')]//a").get_attribute("href")

                    driver.execute_script("window.open(arguments[0]);", post_link)
                    driver.switch_to.window(driver.window_handles[1])
                    time.sleep(2)
                    comments = driver.find_elements(By.CSS_SELECTOR, "span.comments-comment-item__main-content")[:max_comments]
                    comment_texts = [comment.text or "unknown" for comment in comments]
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

                    post_data.append({
                        "source": "LinkedIn", "platform": "LinkedIn", "type": "post", "post_id": post_link.split("/")[-2],
                        "date": date, "text": text, "retweets": "N/A", "likes": likes,
                        "user_location": "unknown", "country": "unknown", "comments": ";".join(comment_texts) or "none"
                    })
                except Exception as e:
                    print(f"Error scraping LinkedIn post: {e}")
                    continue

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            scrolls += 1

        df = pd.DataFrame(post_data)
        df.to_csv(output_file, index=False)
        print(f"Collected {len(post_data)} LinkedIn posts with comments. Saved to '{output_file}'.")
    except Exception as e:
        print(f"Fatal error in LinkedIn scraping: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    for query in query_variations:
        collect_linkedin_data(query=query, output_file=f"csv_files/linkedin_data_{query.replace(' ', '_')}.csv")