from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import os
from dotenv import load_dotenv
from query_variations import query_variations
from datetime import datetime
from pathlib import Path

def clear_cache_and_cookies(driver):
    driver.delete_all_cookies()
    print("Cache and cookies cleared.")

def login_to_x(driver, wait, username, password, email):
    driver.get("https://x.com/login")
    print("Attempting login...")
    wait.until(EC.presence_of_element_located((By.NAME, "text"))).send_keys(username + Keys.RETURN)
    time.sleep(2)
    try:
        verification_field = wait.until(EC.presence_of_element_located((By.NAME, "text")))
        verification_title = driver.find_element(By.ID, "modal-header").text
        if "email" in verification_title.lower():
            print("Verification step detected. Re-entering email...")
            verification_field.send_keys(email + Keys.RETURN)
        else:
            print("Verification step detected. Re-entering username...")
            verification_field.send_keys(username + Keys.RETURN)
        time.sleep(5)
        print("Verification submitted. Current URL:", driver.current_url)
    except:
        try:
            verification_field = wait.until(EC.presence_of_element_located((By.NAME, "text")))
            print("Verification step detected. Re-entering phone number...")
            verification_field.send_keys(username + Keys.RETURN)
            time.sleep(5)
            print("Verification submitted. Current URL:", driver.current_url)
        except:
            print("No verification step detected, proceeding...")
    wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(password + Keys.RETURN)
    time.sleep(5)
    print("Password entered. Current URL:", driver.current_url)
    if "login" in driver.current_url:
        print("Login failed. Check credentials, CAPTCHA, or additional verification (e.g., SMS code).")
        print("Pausing for manual intervention. Solve any CAPTCHA or enter SMS code in the browser, then press Enter here.")
        input("Press Enter to continue after manual verification...")
        print("Resuming after manual input. Current URL:", driver.current_url)

def collect_x_data(driver, wait, query="Tamim ibn Hamad Al Thani", max_posts=20, max_comments=5):
    url = f"https://x.com/search?q={query}&lang=en"
    driver.get(url)
    time.sleep(5)
    print(f"Searching X for '{query}'... Page title: {driver.title}")
    print("Switching to 'Latest' tab...")
    latest_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Latest']")))
    latest_tab.click()
    time.sleep(3)
    print("Switched to Latest tab. Current URL:", driver.current_url)
    post_data = []
    scrolls = 0
    retries = 0
    max_retries = 3
    while len(post_data) < max_posts and scrolls < 10:
        try:
            posts = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-testid='tweetText']")))
            print(f"Found {len(posts)} posts on scroll {scrolls + 1}")
            for post in posts[:max_posts - len(post_data)]:
                try:
                    text = post.text or "unknown"
                    article = post.find_element(By.XPATH, "./ancestor::article")
                    date = (article.find_element(By.XPATH, ".//time").get_attribute("datetime") 
                            if article.find_elements(By.XPATH, ".//time") else "unknown")
                    retweets = (article.find_element(By.XPATH, ".//div[@data-testid='retweet']").text 
                                if article.find_elements(By.XPATH, ".//div[@data-testid='retweet']") else "unknown")
                    likes = (article.find_element(By.XPATH, ".//div[@data-testid='like']").text 
                             if article.find_elements(By.XPATH, ".//div[@data-testid='like']") else "unknown")
                    post_link = (article.find_element(By.XPATH, ".//a[@role='link'][.//time]").get_attribute("href") 
                                 if article.find_elements(By.XPATH, ".//a[@role='link'][.//time]") else "unknown")
                    user_avatar = (article.find_element(By.XPATH, ".//div[@data-testid='UserAvatar-Container-validatedev']/img").get_attribute("src") 
                                   if article.find_elements(By.XPATH, ".//div[@data-testid='UserAvatar-Container-validatedev']/img") else "unknown")
                    user_display_name = (article.find_element(By.XPATH, ".//div[@data-testid='User-Name']//div[contains(@class, 'r-bcqeeo')]//span[contains(@class, 'r-poiln3')]/span").text 
                                 if article.find_elements(By.XPATH, ".//div[@data-testid='User-Name']//div[contains(@class, 'r-bcqeeo')]//span[contains(@class, 'r-poiln3')]/span") else "unknown")
                    user_name = (article.find_element(By.XPATH, ".//div[@data-testid='User-Name']//div[contains(@class, 'r-dnmrzs')]//span[contains(@class, 'r-poiln3')]").text 
                                 if article.find_elements(By.XPATH, ".//div[@data-testid='User-Name']//div[contains(@class, 'r-dnmrzs')]//span[contains(@class, 'r-poiln3')]") else "unknown")
                    print(f"Scraping post: {text[:30]}... Date: {date}, Retweets: {retweets}, Likes: {likes}, Link: {post_link}, User: {user_display_name} ({user_name}), Avatar: {user_avatar}")
                    if post_link != "unknown":
                        driver.execute_script("window.open(arguments[0]);", post_link)
                        driver.switch_to.window(driver.window_handles[1])
                        time.sleep(2)
                        comments = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='tweetText']")[:max_comments]
                        comment_texts = [comment.text or "unknown" for comment in comments]
                        print(f"Post {post_link}: {len(comment_texts)} comments found")
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    else:
                        comment_texts = ["none"]
                    post_data.append({
                        "source": "X", "platform": "X", "type": "post", "post_id": post_link.split("/")[-1] if post_link != "unknown" else "unknown",
                        "date": date, "text": text, "retweets": retweets, "likes": likes,
                        "user_location": "unknown", "country": "unknown", "comments": ";".join(comment_texts) or "none",
                        "user_display_name": user_display_name, "user_name": user_name, "user_avatar": user_avatar
                    })
                except Exception as e:
                    print(f"Error scraping post: {e}")
                    continue
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            scrolls += 1
        except Exception as e:
            print(f"Error finding posts on scroll {scrolls + 1}: {e}")
            retries += 1
            if retries > max_retries:
                print("Max retries reached. Exiting...")
                break
            print("Retrying...")
            driver.refresh()
            time.sleep(5)
    print(f"Total posts collected: {len(post_data)}")
    return post_data

def main(output_file=None):
    load_dotenv()
    email = os.getenv("X_EMAIL")
    password = os.getenv("X_PASSWORD")
    if not email or not password:
        raise ValueError("X_EMAIL and X_PASSWORD must be set in .env")

    # Ensure output directory exists
    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        output_file = str(Path(__file__).parent.parent.parent / "data" / "raw" / f"x_data_{today}.csv")
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    username = os.getenv("X_USERNAME")
    if not username:
        raise ValueError("X_USERNAME must be set in .env")

    options = Options()
    options.headless = True  # Keep False for debugging
    options.add_argument("--disable-blink-features=AutomationControlled")  # Avoid bot detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    options.add_argument("--no-sandbox")  # Additional evasion
    options.add_argument("--disable-dev-shm-usage")  # Stability on some systems
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)
    all_post_data = []
    try:
        clear_cache_and_cookies(driver)
        login_to_x(driver, wait, username, password, email)
        for query in query_variations:
            all_post_data.extend(collect_x_data(driver, wait, query=query))
    except Exception as e:
        print(f"Fatal error in X scraping: {e}")
    finally:
        df = pd.DataFrame(all_post_data)
        df.to_csv(output_file, index=False)
        print(f"Collected {len(all_post_data)} X posts with comments. Saved to '{output_file}'.")
        driver.quit()

if __name__ == "__main__":
    today = datetime.now().strftime("%Y%m%d")
    output_path = Path(__file__).parent.parent.parent / "data" / "raw" / f"x_data_{today}.csv"
    main(output_file=str(output_path))