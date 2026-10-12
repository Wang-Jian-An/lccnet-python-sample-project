import asyncio
from typing import Optional
from playwright.async_api import Page
from shared.utility import open_playwright_page, close_playwright

@open_playwright_page
async def retrieve_software_list(page: Page, url: str) -> list[tuple[str, str]]:
    """
    從 Azure VM 定價頁面擷取所有可選的 OS/Software 選項。

    導覽至指定 URL 後，等待頁面完全載入（networkidle），
    再從「OS/Software」下拉選單中讀取所有選項的 value 與顯示文字，
    組合成 (value, text) 元組的序列供後續迭代使用。

    Args:
        page (Page): 由 `@open_playwright_page` 裝飾器自動注入的 Playwright Page 實體。
                     呼叫端不需傳入此參數。
        url (str): Azure VM 定價頁面的基礎 URL，例如：
                   ``https://azure.microsoft.com/en-us/pricing/details/virtual-machines/``

    Returns:
        zip[tuple[str, str]]: 包含 (option_value, option_text) 元組的可迭代物件。
            - option_value (str): URL path suffix，例如 ``"linux/"``、``"windows/"``。
            - option_text (str): 下拉選單的顯示文字，例如 ``"Linux"``、``"Windows"``。

    Raises:
        playwright._impl._errors.TimeoutError: 若頁面未能在預設逾時時間內載入完成。
    """
    options_value = await page.get_by_label("OS/Software") \
        .locator("option") \
        .evaluate_all("element => element.map(el => el.value.trim())")
    options_text = await page.get_by_label("OS/Software") \
        .locator("option") \
        .evaluate_all("element => element.map(el => el.text.trim())")
    return zip(options_value, options_text)

@open_playwright_page
async def filter_region_and_retrieve_table(
    page: Page,
    url: str,
    region_name: Optional[str] = None
) -> list[dict[str, list[str]]]:
    """
    導覽至指定的 Azure 服務定價頁面，依序切換所有（或指定）地區，
    並擷取各地區的定價表格 HTML。

    執行流程：
        1. 載入頁面並等待網路閒置（networkidle）。
        2. 將「Display pricing by」切換為 ``hour``（小時計費）。
        3. 讀取「Region」下拉選單中的所有地區選項。
        4. 依序切換至每個地區（或僅切換至符合 `region_name` 的地區），
           等待表格重新渲染後擷取所有 ``<table>`` 的 outerHTML。
        5. 回傳以地區 value 為 key、HTML 字串列表為 value 的字典清單。

    Args:
        page (Page): 由 `@open_playwright_page` 裝飾器自動注入的 Playwright Page 實體。
                     呼叫端不需傳入此參數。
        url (str): 目標 Azure 服務定價頁面的完整 URL，例如：
                   ``https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/``
        region_name (Optional[str]): 若指定，則只擷取 option value 完全符合此字串的地區；
                                     若為 ``None``（預設），則遍歷所有地區。

    Returns:
        list[dict[str, list[str]]]: 每個元素代表一個地區的資料，格式為：
            ``[{"eastus": ["<table>...</table>", ...]}, ...]``
            - key：地區的 option value 字串。
            - value：該地區頁面上所有定價表格的 outerHTML 字串清單。

    Raises:
        playwright._impl._errors.TimeoutError: 若頁面或選單元素未能在預設逾時時間內就緒。
    """


    await page.goto(url, wait_until="networkidle")

    # Choose the unit price
    await page \
        .get_by_label("Display pricing by") \
        .select_option("hour")
    await asyncio.sleep(1)

    # Collect regions
    region_options = await page \
        .get_by_label("Region") \
        .locator("option") \
        .evaluate_all("element => element.map(el => el.value.trim())")

    # Filter region and retrieve price table
    result = list()
    for option in region_options:
        await page \
            .get_by_label("Region") \
            .select_option(value=option)
        await asyncio.sleep(1)

        tables = await page \
            .locator('table.data-table__table.data-table__table--pricing') \
            .evaluate_all('element => element.map(el => el.outerHTML)')
        result.append(
            {option: tables}
        )
    
    return result


async def main():
    """
    Azure VM 定價爬蟲的主進入點。

    執行流程：
        1. 從 Azure VM 定價頁面擷取所有 OS/Software 選項（如 Linux、Windows）。
        2. 對每個選項並發發起爬蟲任務，透過 BrowserPool 的 Semaphore 自動節流。
        3. 完成後統一關閉 Browser 行程。
    """

    try:
        # 1. Retrieve the software list
        options = await retrieve_software_list(url=url)

        # 2. Retrieve the price table for each OS/Software option concurrently
        # Semaphore in BrowserPool will throttle to max_concurrency at a time
        all_results = await asyncio.gather(*[
            filter_region_and_retrieve_table(url=f"{url}{key}")
            for key, value in options
        ])

        print(f"全部爬取完畢，共 {len(all_results)} 組資料。")

    finally:
        # 3. Release the browser process on exit
        await close_playwright()


if __name__ == '__main__':
    asyncio.run(main())

