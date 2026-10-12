import asyncio
from typing import Optional
from bs4 import BeautifulSoup
from playwright.async_api import Page
from shared.utility import open_playwright_page, close_playwright


@open_playwright_page
async def compute_mode_links(page: Page, url: str) -> list[str]:
    """
    從 GCP 運算服務定價頁面擷取各運算類別的 HTML 區塊。

    導覽至指定 URL 後，定位頁面內的類別表格，
    擷取每個類別儲存格（`<div>`）的 outerHTML，
    供 `get_cat_name_and_link()` 後續解析類別名稱與連結。

    Args:
        page (Page): 由 `@open_playwright_page` 裝飾器自動注入的 Playwright Page 實體。
                     呼叫端不需傳入此參數。
        url (str): GCP 運算服務定價頁面的 URL，例如：
                   ``https://cloud.google.com/products/compute/pricing``

    Returns:
        list[str]: 各類別儲存格的 outerHTML 字串清單，每個元素包含
                   類別名稱文字與指向詳細定價頁面的超連結。

    Raises:
        playwright._impl._errors.TimeoutError: 若頁面主體或類別表格未能在逾時時間內就緒。
    """
    await page.goto(url, wait_until="commit", timeout=60000)
    await page.wait_for_selector("main, body", timeout=15000)
    print("頁面載入成功！")

    table_element = page.locator('table.xIA6mc.UAquKe.wVBoU.sBciVd')
    categories = await table_element.locator('tr > td.D4dSv[rowspan="1"] > div').all()
    return [await i.evaluate('el => el.outerHTML') for i in categories]


def get_cat_name_and_link(req_text: str) -> Optional[tuple[str, str]]:
    """
    從單一類別儲存格的 HTML 字串中解析出類別名稱與定價頁面連結。

    使用 BeautifulSoup 解析傳入的 HTML 片段，
    分別尋找第一個 ``<p>`` 標籤（類別名稱）與第一個 ``<a>`` 標籤（連結）。
    若任一元素不存在，回傳 ``None`` 以便呼叫端過濾無效項目。

    Args:
        req_text (str): 單一類別儲存格的 outerHTML 字串，
                        通常來自 `compute_mode_links()` 的回傳值。

    Returns:
        Optional[tuple[str, str]]: 解析成功時回傳 ``(category_name, href)``：
            - category_name (str): 類別的顯示名稱，例如 ``"General purpose"``。
            - href (str): 指向該類別定價頁面的完整或相對 URL。
            若 ``<p>`` 或 ``<a>`` 任一缺失，回傳 ``None``。
    """
    soup = BeautifulSoup(req_text, 'html.parser')
    cat_tag = soup.find('p')
    a_tag = soup.find('a')
    if not cat_tag or not a_tag:
        return None
    return cat_tag.text.strip(), a_tag.get('href')


@open_playwright_page
async def retrieve_price_table_all_regions(
    page: Page,
    url: str,
    region_name: Optional[str] = None
) -> list[dict[str, list[str]]]:
    """
    導覽至指定的 GCP 服務定價頁面，依序切換所有（或指定）地區，
    並擷取各地區的定價表格 HTML。

    執行流程：
        1. 載入頁面並等待網路閒置（networkidle）。
        2. 定位頁面上的地區 combobox，展開後讀取所有可選地區。
        3. 依序點選每個地區（或僅點選符合 `region_name` 的地區），
           等待表格重新渲染後擷取所有 ``<table>`` 的 outerHTML。
        4. 若下拉選單因頁面捲動而消失，自動重新展開後再切換。

    Args:
        page (Page): 由 `@open_playwright_page` 裝飾器自動注入的 Playwright Page 實體。
                     呼叫端不需傳入此參數。
        url (str): 目標 GCP 服務類別定價頁面的完整 URL，例如：
                   ``https://cloud.google.com/compute/all-pricing#n1_standard_machine_types``
        region_name (Optional[str]): 若指定，則只擷取顯示文字包含此字串的地區後立即回傳；
                                     若為 ``None``（預設），則遍歷所有地區。

    Returns:
        list[dict[str, list[str]]]: 每個元素代表一個地區的資料，格式為：
            ``[{"Iowa (us-central1)": ["<table>...</table>", ...]}, ...]``
            - key：地區的完整顯示名稱字串。
            - value：該地區頁面上所有定價表格的 outerHTML 字串清單。

    Raises:
        playwright._impl._errors.TimeoutError: 若頁面、combobox 或選項元素
                                               未能在逾時時間內就緒。
    """
    await page.goto(url, timeout=60000, wait_until='networkidle')

    region_combobox = page.locator('div[role="combobox"]').first
    await region_combobox.wait_for(state="visible", timeout=30000)
    await region_combobox.click()
    await asyncio.sleep(0.5)

    options_locator = page.locator('div.UAquKe.Idevi > div.DIc0oc.xLdFee') \
        .first \
        .locator('ul[role="listbox"] > li[role="option"]')
    await options_locator.first.wait_for(state="attached", timeout=10000)

    count = await options_locator.count()
    print(f"[{url}] 找到 {count} 個地區選項")

    results = []
    for idx in range(count):
        opt = options_locator.nth(idx)
        raw_text = await opt.text_content()
        curr_region = raw_text.strip() if raw_text else f"region_{idx}"

        if region_name and region_name not in curr_region:
            continue

        try:
            if not await opt.is_visible():
                await region_combobox.click()
                await opt.wait_for(state="visible", timeout=3000)

            await opt.click()
            await asyncio.sleep(1)
        except Exception as e:
            print(f"切換地區 {curr_region} 失敗: {e}")
            continue

        table_html_list = await page.locator("div.x7TZPe > table").evaluate_all(
            "tables => tables.map(t => t.outerHTML)"
        )
        results.append({curr_region: table_html_list})

        if region_name:
            break

    return results


async def main():
    """
    GCP 運算服務定價爬蟲的主進入點。

    執行流程：
        1. 從 GCP 運算服務定價總覽頁面擷取所有子類別名稱與連結。
        2. 過濾掉解析失敗的無效項目。
        3. 對每個子類別並發發起全地區爬蟲任務，
           透過 BrowserPool 的 Semaphore 自動節流（一次最多 max_concurrency 個 Context）。
        4. 完成後統一關閉 Browser 行程。
    """

    try:
        # 1. 爬取類別列表
        computing_table = await compute_mode_links(url=url)
        cat_pairs = [get_cat_name_and_link(html) for html in computing_table]
        valid_pairs = [pair for pair in cat_pairs if pair is not None]

        print(f"共取得 {len(valid_pairs)} 個有效類別")

        # 2. 同時發起多任務
        # 即使傳入 10 個任務，utility.py 內的 Semaphore 會自動排隊（一次只跑 2 個 Context）
        all_results = await asyncio.gather(*[
            retrieve_price_table_all_regions(url=link)
            for _, link in valid_pairs
        ])

        print(f"全部爬取完畢，共 {len(all_results)} 組資料。")

    finally:
        # 3. 結束時統一關閉瀏覽器行程
        await close_playwright()


if __name__ == "__main__":
    asyncio.run(main())