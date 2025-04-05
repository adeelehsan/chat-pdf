import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import os
from urllib.parse import urljoin

BASE_URL = "https://find-and-update.company-information.service.gov.uk"

PAGE_LOAD_DELAY_MS = 1500  # milliseconds after basic load
INTERACTION_DELAY_MS = 3000  # milliseconds after clicks/checks
DOWNLOAD_TRIGGER_DELAY_MS = 1000  # milliseconds after click before expecting download
FILTER_UPDATE_TIMEOUT_MS = 25000  # Max time to wait for filter results to load (increased slightly)


def download_company_pdfs(company_number: str, download_folder: str) -> list[str]:
    """
    Finds and downloads 'accounts' related PDFs from Companies House using Playwright,
    applying the 'Accounts' filter first. (SYNC API VERSION)

    Args:
        company_number: The company registration number.
        download_folder: The base folder to save downloaded PDFs.

    Returns:
        A list of file paths to the successfully downloaded PDFs.
    """
    if not company_number:
        raise ValueError("Invalid company number provided.")

    company_specific_folder = os.path.join(download_folder, str(company_number))
    os.makedirs(company_specific_folder, exist_ok=True)

    downloaded_files = []
    filing_history_url = f"{BASE_URL}/company/{company_number}/filing-history"

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                # Go to the page, wait for network to be mostly idle
                page.goto(filing_history_url, wait_until='domcontentloaded', timeout=60000)  # 60s timeout
                page.wait_for_timeout(PAGE_LOAD_DELAY_MS)  # Explicit delay
            except PlaywrightTimeoutError:
                print(f"Error: Timeout loading initial page {filing_history_url}")
                raise
            except Exception as e:
                print(f"Error navigating to initial page {filing_history_url}: {e}")
                raise

            try:

                accounts_checkbox_locator = page.locator('#filter-category-accounts')
                accounts_checkbox_locator.wait_for(state='visible', timeout=12000)
                accounts_checkbox_locator.check()
                page.wait_for_timeout(INTERACTION_DELAY_MS)
                page.wait_for_load_state('networkidle', timeout=FILTER_UPDATE_TIMEOUT_MS)

            except PlaywrightTimeoutError as te:
                print(f"Error: Timeout occurred during filter application: {te}")
                raise TimeoutError(
                    f"Timeout applying filter or waiting for results on {page.url}") from te
            except Exception as e:
                print(f"Error applying filter: {e}")
                raise RuntimeError(f"Failed to apply filter on {page.url}") from e

            current_page_url = page.url

            while current_page_url:

                if page.url != current_page_url:
                    try:
                        page.goto(current_page_url, wait_until='domcontentloaded', timeout=60000)
                        page.wait_for_timeout(PAGE_LOAD_DELAY_MS)
                    except Exception as nav_exc:
                        print(f"ERROR: Failed to navigate to {current_page_url}: {nav_exc}")
                        current_page_url = None

                # Find the main table containing the filing history
                table_locator = page.locator('table#fhTable')
                try:
                    table_locator.wait_for(state='visible', timeout=15000)
                except PlaywrightTimeoutError:
                    page_content = page.content()
                    if "company number was not found" in page_content.lower():
                        print(f"Company number {company_number} seems to have disappeared or page error.")
                    break

                rows = table_locator.locator('tr')
                row_count = rows.count()  # No await

                for i in range(1, row_count):
                    row = rows.nth(i)
                    date_cell = row.locator('td:first-child')
                    description_cell = row.locator('td:nth-child(3)')
                    last_cell = row.locator('td:last-child')

                    if description_cell.is_visible() and last_cell.is_visible():
                        pdf_link_tag = last_cell.locator('a:has-text("View PDF")')

                        if pdf_link_tag.count() > 0:  # Check if the specific link was found
                            pdf_link_tag = pdf_link_tag.first  # Should be unique, but take first just in case

                            link_href = pdf_link_tag.get_attribute('href') or ""

                            if link_href:
                                print(f"Row {i}: Found PDF link: {link_href}")

                                # --- Get Metadata ---
                                filing_date = "unknown_date"
                                if date_cell.is_visible():
                                    filing_date = date_cell.inner_text().strip() or "unknown_date"
                                else:
                                    print(
                                        f"Row {i}: Date cell (td:first-child) not visible.")

                                description_text = "no_description"
                                if description_cell.is_visible():
                                    description_text = description_cell.inner_text().strip() or "no_description"
                                else:
                                    print(f"Row {i}: Description cell (td:nth-child(3)) not visible.")

                                # Sanitize date for filename
                                safe_date = "".join(
                                    c if c.isalnum() else "_" for c in filing_date)

                                # --- Extract Unique ID from href ---
                                unique_id_match = re.search(
                                    r'/filing-history/([^/]+)/document', link_href)
                                if unique_id_match:
                                    unique_id = unique_id_match.group(1)
                                else:
                                    try:
                                        path_part = link_href.split('?')[0]
                                        unique_id = path_part.split('/')[-2]
                                        if not unique_id or unique_id == "filing-history":
                                            raise IndexError
                                    except IndexError:
                                        unique_id = f"doc_{i}_{len(downloaded_files)}"  # Fallback unique ID

                                # --- Generate Filename ---
                                safe_desc = "".join(c if c.isalnum() else "_" for c in
                                                    description_text[:40]).strip('_') or "filing"
                                filename = f"{safe_date}_{safe_desc}_{unique_id}.pdf"
                                save_path = os.path.join(company_specific_folder, filename)

                                # --- Download Logic ---
                                if not os.path.exists(save_path):
                                    try:
                                        with page.expect_download(timeout=300000) as download_info:
                                            # Click the specific "View PDF" link tag
                                            pdf_link_tag.click()

                                        download = download_info.value
                                        failure = download.failure()  # Check failure status synchronously
                                        if failure:
                                            print(f"Error: Download failed! Reason: {failure}")
                                        else:
                                            download.save_as(save_path)
                                            print(f"Successfully saved: {filename}")
                                            downloaded_files.append(save_path)
                                            page.wait_for_timeout(INTERACTION_DELAY_MS)

                                    except PlaywrightTimeoutError:
                                        print(f"Error: Download did not start within timeout for link: {link_href}")
                                    except Exception as e:
                                        print(f"Error during download process for {link_href}: {e}")

                # --- Pagination ---
                next_link_locator = page.locator('a[rel="next"]')
                if next_link_locator.is_visible():
                    next_page_relative_url = next_link_locator.get_attribute('href')
                    if next_page_relative_url:
                        current_page_url = urljoin(BASE_URL, next_page_relative_url)
                        print(f"Found next page link: {current_page_url}")
                    else:
                        print("Next link found, but no href attribute.")
                        current_page_url = None
                else:
                    print("No active 'Next' page link found.")
                    current_page_url = None  # Exit loop

        except Exception as e:
            print(f"An unexpected error occurred during Playwright scraping: {e}")
        finally:
            if browser:
                browser.close()

    return downloaded_files
