from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import pandas as pd
import time
import os
from dotenv import load_dotenv
from query_variations import query_variations

def collect_instagram_data(query="sheikhtamim", max_posts=20, max_comments=5, output_file="instagram_data.csv"):
    load_dotenv()
    username = os.getenv("INSTAGRAM_USERNAME")
    password = os.getenv("INSTAGRAM_PASSWORD")
    if not username or not password:
        raise ValueError("INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD must be set in .env")

    options = Options()
    options.headless = False  # Set to True after testing
    driver = webdriver.Chrome(options=options)
    try:
        # Login to Instagram
        driver.get("https://www.instagram.com/accounts/login/")
        time.sleep(3)
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password + Keys.RETURN)
        time.sleep(5)  # Wait for login and possible "Save Info" prompt
        try:
            driver.find_element(By.XPATH, "//button[text()='Not Now']").click()  # Skip "Save Info"
        except:
            pass
        time.sleep(2)

        # Search and scrape
        url = f"https://www.instagram.com/explore/tags/{query}/"
        driver.get(url)
        print(f"Scraping Instagram for '#{query}'...")

        post_data = []
        scrolls = 0
        while len(post_data) < max_posts and scrolls < 10:
            posts = driver.find_elements(By.CSS_SELECTOR, "article div._aagv")
            for post in posts[:max_posts - len(post_data)]:
                try:
                    post_link = post.find_element(By.XPATH, ".//ancestor::article//a").get_attribute("href")
                    driver.execute_script("window.open(arguments[0]);", post_link)
                    driver.switch_to.window(driver.window_handles[1])
                    time.sleep(2)

                    text = driver.find_element(By.CSS_SELECTOR, "div._a9zs").text or "unknown"
                    date = driver.find_element(By.CSS_SELECTOR, "time").get_attribute("datetime") or "unknown"
                    likes = driver.find_element(By.XPATH, "//span[@class='x1lliihq']").text or "unknown"
                    comments = driver.find_elements(By.CSS_SELECTOR, "ul._a9ym li._a9zj")[:max_comments]
                    comment_texts = [comment.find_element(By.CSS_SELECTOR, "span").text or "unknown" for comment in comments]

                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

                    post_data.append({
                        "source": "Instagram", "platform": "Instagram", "type": "post", "post_id": post_link.split("/")[-2],
                        "date": date, "text": text, "retweets": "N/A", "likes": likes,
                        "user_location": "unknown", "country": "unknown", "comments": ";".join(comment_texts) or "none"
                    })
                except Exception as e:
                    print(f"Error scraping Instagram post: {e}")
                    continue

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            scrolls += 1

        df = pd.DataFrame(post_data)
        df.to_csv(output_file, index=False)
        print(f"Collected {len(post_data)} Instagram posts with comments. Saved to '{output_file}'.")
    except Exception as e:
        print(f"Fatal error in Instagram scraping: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    for query in query_variations:
        collect_instagram_data(query=query, output_file=f"csv_files/instagram_data_{query.replace(' ', '_')}.csv")