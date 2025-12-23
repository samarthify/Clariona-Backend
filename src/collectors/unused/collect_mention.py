from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
from dotenv import load_dotenv
from datetime import datetime
import requests
import shutil
from pathlib import Path

def collect_mention_data(output_file=None):
    load_dotenv()
    api_key = os.getenv("MENTION_API_KEY")
    account_id = os.getenv("MENTION_ACCOUNT_ID")
    alert_id = os.getenv("MENTION_ALERT_ID")
    if not all([api_key, account_id, alert_id]):
        raise ValueError("MENTION_API_KEY, MENTION_ACCOUNT_ID, and MENTION_ALERT_ID must be set in .env")

    # Ensure output directory exists
    if output_file is None:
        today = datetime.now().strftime("%Y%m%d")
        output_file = str(Path(__file__).parent.parent.parent / "data" / "raw" / f"mention_data_{today}.csv")
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    email = os.getenv("MENTION_EMAIL")
    password = os.getenv("MENTION_PASSWORD")
    if not email or not password:
        raise ValueError("MENTION_EMAIL and MENTION_PASSWORD must be set in .env")

    options = Options()
    options.headless = True  # Keep False for debugging
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    try:
        # Step 1: Open login page
        driver.get("https://web.mention.com/en#login")
        print("Opened Mention login page. Current URL:", driver.current_url)
        time.sleep(3)

        # Step 2: Log in
        print("Attempting login to Mention...")
        email_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        email_field.send_keys(email)
        password_field = driver.find_element(By.NAME, "password")
        password_field.send_keys(password + Keys.RETURN)
        time.sleep(5)
        print("Login attempted. Current URL:", driver.current_url)

        if "login" in driver.current_url.lower():
            print("Login failed. Pausing for manual intervention (e.g., CAPTCHA)...")
            input("Press Enter after resolving any issues...")
            print("Resuming. Current URL:", driver.current_url)

        # Step 3: Click Feed button
        print("Locating Feed button...")
        feed_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "icon-feed")))
        feed_button.click()
        time.sleep(5)  # Wait for feed to load
        print("Clicked Feed button. Current URL:", driver.current_url)

        # Step 4: Click "View all mentions" button
        print("Locating 'View all mentions' button...")
        try:
            view_all_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//div[contains(text(), 'View all mentions')]]")
            ))
            view_all_button.click()
            print("Clicked 'View all mentions' button.")
            time.sleep(5)  # Wait for mentions to load
        except Exception as e:
            print(f"Failed to find 'View all mentions' button with text: {e}")
            # Try alternative selectors
            try:
                view_all_button = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[data-userflowid='feed:alert-overview.header.go-to-feed.button']")
                ))
                view_all_button.click()
                print("Clicked 'View all mentions' button using data-userflowid.")
                time.sleep(5)
            except Exception as e2:
                print(f"Failed to find 'View all mentions' button with data-userflowid: {e2}")
                raise

        # Step 5: Click Export button (using aria-label)
        print("Locating Export button...")
        try:
            export_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[@aria-label='Export mentions']")
            ))
            export_button.click()
            print("Clicked Export button using aria-label.")
        except Exception as e:
            print(f"Failed to find Export button with aria-label: {e}")
            export_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(@class, 'MuiIconButton-root')]//svg[contains(@class, 'new-icons-download')]")
            ))
            export_button.click()
            print("Clicked Export button using fallback (icon class).")
        time.sleep(2)  # Wait for dropdown to appear

        # Step 6: Select "Export mentions (CSV)" from the dropdown
        print("Selecting CSV export option...")
        csv_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//li[contains(., 'Export mentions (CSV)')]")
        ))
        csv_option.click()
        print("Selected CSV export option.")
        time.sleep(2)  # Wait for confirmation dialog

        # Step 7: Click "Export Page" link
        print("Locating Export Page link...")
        export_page_link = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(., 'Export Page')]")
        ))
        export_page_link.click()
        print("Clicked Export Page link. Current URL:", driver.current_url)
        time.sleep(10)  # Wait for export to process

        # Step 8: Refresh the page
        print("Refreshing export page...")
        driver.refresh()
        time.sleep(5)  # Wait for table to load

        # Step 9: Find and download the latest CSV
        print("Locating latest export row...")
        export_rows = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//table[@class='imbat-table']/tbody/tr")
        ))
        if not export_rows:
            raise Exception("No export rows found in the table.")

        # Assume the first row is the latest
        latest_row = export_rows[0]
        download_link = latest_row.find_element(By.XPATH, ".//a[contains(., 'CSV')]")
        download_url = download_link.get_attribute("href")
        print(f"Found latest export. Download URL: {download_url}")

        # Download the CSV file
        temp_file = "temp_mention_export.csv"
        response = requests.get(download_url)
        if response.status_code == 200:
            with open(temp_file, "wb") as f:
                f.write(response.content)
            print(f"Downloaded CSV to temporary file: {temp_file}")
        else:
            raise Exception(f"Failed to download CSV. Status code: {response.status_code}")

        # Step 10: Move the temporary file to the output location
        shutil.move(temp_file, output_file)
        print(f"Moved downloaded CSV to '{output_file}'.")

    except Exception as e:
        print(f"Error in Mention export process: {e}")
    finally:
        # Clean up temporary file if it still exists
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                print(f"Cleaned up temporary file: {temp_file}")
            except:
                print(f"Failed to clean up temporary file: {temp_file}")
        driver.quit()

if __name__ == "__main__":
    today = datetime.now().strftime("%Y%m%d")
    output_path = Path(__file__).parent.parent.parent / "data" / "raw" / f"mention_data_{today}.csv"
    collect_mention_data(output_file=str(output_path))