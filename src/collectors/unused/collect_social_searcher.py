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
from datetime import datetime
from query_variations import query_variations
from pathlib import Path

def collect_social_searcher(output_file=None):
    load_dotenv()
    email = os.getenv("SOCIAL_SEARCHER_EMAIL")
    password = os.getenv("SOCIAL_SEARCHER_PASSWORD")
    if not email or not password:
        raise ValueError("SOCIAL_SEARCHER_EMAIL and SOCIAL_SEARCHER_PASSWORD must be set in .env")

    # Ensure output directory exists
    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        output_file = str(Path(__file__).parent.parent.parent / "data" / "raw" / f"social_searcher_data_{today}.csv")
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    options = Options()
    options.headless = True  # Set to True for production
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    all_data = []

    try:
        # Step 1: Open main page
        driver.get("https://www.social-searcher.com/")
        print("Opened main page. Current URL:", driver.current_url)
        time.sleep(3)  # Wait for page load

        # Step 2: Click login button
        login_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "mainpage-header__login_text")))
        login_button.click()
        print("Clicked login button. Waiting for popup...")
        time.sleep(3)  # Wait for popup to appear

        # Step 3: Log in via popup
        print("Attempting login to Social Searcher...")
        email_field = wait.until(EC.presence_of_element_located((By.ID, "loginuseremail")))
        email_field.send_keys(email)
        password_field = driver.find_element(By.ID, "loginuserpass")
        password_field.send_keys(password)
        submit_button = driver.find_element(By.CLASS_NAME, "popup-form__btn")
        submit_button.click()
        time.sleep(5)  # Wait for login to complete
        print("Login attempted. Current URL:", driver.current_url)

        if "login" in driver.current_url.lower() or "login" in driver.title.lower():
            print("Login failed. Pausing for manual intervention (e.g., CAPTCHA)...")
            input("Press Enter after resolving any issues...")
            print("Resuming. Current URL:", driver.current_url)

        # Step 4: Click saved search "Tamim ibn Hamad Al Thani"
        print("Locating 'Saved Searches' section...")
        saved_searches_label = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "mainscreen-form__label")))
        if "Saved Searches" in saved_searches_label.text:
            print("Found 'Saved Searches' label.")
            saved_search_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@class='mainscreen-form__example' and text()='Tamim ibn Hamad Al Thani']")))
            saved_search_link.click()
            time.sleep(5)  # Wait for search results to load
            print(f"Clicked saved search 'Tamim ibn Hamad Al Thani'. Current URL: {driver.current_url}, Page title: {driver.title}")
        else:
            raise Exception("Could not find 'Saved Searches' section on the page.")

        # Step 5: Scroll to load more results
        scrolls = 0
        last_height = driver.execute_script("return document.body.scrollHeight")
        while scrolls < 5:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("No more results to load.")
                break
            last_height = new_height
            scrolls += 1
            print(f"Scroll {scrolls} completed.")

        # Step 6: Extract results
        results = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "rezults-item")))
        print(f"Found {len(results)} results.")
        
        for result in results:
            try:
                # Determine source type from icon
                icon = result.find_element(By.CLASS_NAME, "rezults-item__icon").find_element(By.TAG_NAME, "div")
                source_class = icon.get_attribute("class")
                if "rezults-item__web" in source_class:
                    source = "News"
                    platform = result.find_element(By.CLASS_NAME, "rezults-item-user__name").text
                elif "rezults-item__twitter" in source_class:
                    source = "Social Media"
                    platform = "X"
                elif "rezults-item__facebook" in source_class:
                    source = "Social Media"
                    platform = "Facebook"
                elif "rezults-item__instagram" in source_class:
                    source = "Social Media"
                    platform = "Instagram"
                elif "rezults-item__linkedin" in source_class:
                    source = "Social Media"
                    platform = "LinkedIn"
                else:
                    source = "Unknown"
                    platform = "Unknown"

                # Extract user info
                user_info = result.find_element(By.CLASS_NAME, "rezults-item-user__info").text
                date_str = user_info.replace("Posted ", "") if "Posted" in user_info else "unknown"

                # Extract text and URL
                text_elem = result.find_element(By.CLASS_NAME, "rezults-item-text")
                text = text_elem.find_element(By.TAG_NAME, "p").text or "unknown"
                url = text_elem.find_element(By.CLASS_NAME, "rezults-item-text__url").get_attribute("href") or "unknown"

                # Determine country (basic heuristic)
                country = "us" if ".com" in platform.lower() or "cnn" in platform.lower() else \
                         "uk" if ".co.uk" in platform.lower() or "bbc" in platform.lower() else \
                         "uae" if ".ae" in platform.lower() or any(source in platform.lower() for source in ["gulfnews", "khaleejtimes", "thenational"]) else \
                         "unknown"

                if text != "unknown":
                    all_data.append({
                        "source": source,
                        "platform": platform,
                        "type": "post",
                        "post_id": url.split("/")[-1] if url != "unknown" else "unknown",
                        "date": date_str,
                        "text": text,
                        "retweets": "N/A",
                        "likes": "N/A",
                        "user_location": platform,
                        "country": country,
                        "comments": "none"
                    })
                    print(f"Collected: {platform} - {text[:50]}...")

            except Exception as e:
                print(f"Error scraping result: {e}")
                continue

        # Step 7: Save data
        if all_data:
            df = pd.DataFrame(all_data)
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                try:
                    existing_df = pd.read_csv(output_file)
                    df = pd.concat([existing_df, df], ignore_index=True)
                except pd.errors.EmptyDataError:
                    print(f"Warning: The file '{output_file}' is empty. Creating a new file.")
            df.to_csv(output_file, index=False)
            print(f"\nCollected {len(all_data)} total items from Social Searcher. Saved to '{output_file}'.")
        else:
            print("\nNo items collected.")
            df = pd.DataFrame(columns=["source", "platform", "type", "post_id", "date", "text", "retweets", "likes", "user_location", "country", "comments"])
            df.to_csv(output_file, index=False)
            print(f"Created empty '{output_file}' with headers.")

    except Exception as e:
        print(f"Fatal error in Social Searcher scraping: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    today = datetime.now().strftime("%Y%m%d")
    output_path = Path(__file__).parent.parent.parent / "data" / "raw" / f"social_searcher_data_{today}.csv"
    collect_social_searcher(output_file=str(output_path))