# shared/utility.py
import asyncio
from functools import wraps
from typing import Optional, Any
from playwright.async_api import async_playwright, Browser, Playwright

class BrowserPool:
    """
    單例瀏覽器集區管理器，維護全域唯一的 Playwright Browser 實體。

    透過 asyncio.Lock 確保多個協程同時呼叫時，只會啟動一個 Browser 行程；
    透過 asyncio.Semaphore 限制同時開啟的 BrowserContext 數量，
    避免記憶體與 CPU 資源耗盡。

    使用方式：
        直接使用模組層級的 `browser_pool` 全域實例，
        或透過 `@open_playwright_page` 裝飾器自動管理 Context 生命週期。
    """

    def __init__(self, max_concurrency: int = 2, headless: bool = True):
        """
        初始化瀏覽器集區。

        Args:
            max_concurrency (int): 同時允許開啟的 BrowserContext 上限。
                                   WSL 環境建議設為 2~3，避免資源耗盡。
                                   預設為 2。
            headless (bool): 是否以無頭模式（不顯示視窗）啟動瀏覽器。
                             開發偵錯時可設為 False 以觀察頁面行為。
                             預設為 True。
        """
        self.max_concurrency = max_concurrency
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def get_browser(self) -> Browser:
        """
        取得全域唯一的 Browser 實體（Lazy Initialization）。

        首次呼叫時才啟動 Playwright 與 Chromium；後續呼叫若 Browser
        仍處於連線狀態則直接回傳快取實體，不重複啟動。
        使用 asyncio.Lock 確保多個協程並發呼叫時的執行緒安全。

        Returns:
            Browser: 已啟動且可用的 Playwright Chromium Browser 實體。

        Raises:
            playwright._impl._errors.Error: 若 Chromium 無法啟動（例如找不到
                可執行檔或系統資源不足）時拋出。
        """
        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    channel="chrome",
                    headless=self.headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                    ]
                )
            return self._browser

    async def close(self):
        """
        關閉 Browser 與 Playwright 引擎，釋放所有相關系統資源。

        此方法為冪等操作（idempotent）：若 Browser 或 Playwright
        尚未初始化或已關閉，呼叫此方法不會產生錯誤。
        關閉順序為先關閉 Browser，再停止 Playwright，以確保資源正確釋放。

        通常在主程式的 `finally` 區塊中透過 `close_playwright()` 間接呼叫。
        """
        async with self._lock:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

# 初始化全域集區（WSL 建議 max_concurrency 設為 2~3）
browser_pool = BrowserPool(max_concurrency=2, headless=False)


def open_playwright_page(func):
    """
    非同步函式裝飾器，自動管理 Playwright BrowserContext 與 Page 的完整生命週期。

    裝飾器會依序執行以下步驟：
        1. 透過 Semaphore 限制同時執行的 Context 數量，防止資源耗盡。
        2. 從全域 BrowserPool 取得唯一的 Browser 實體。
        3. 建立隔離的 BrowserContext，並注入防自動化偵測腳本
           （覆寫 `navigator.webdriver`），同時設定一般使用者的
           User-Agent、語系與時區，降低被反爬蟲機制封鎖的機率。
        4. 在該 Context 中開啟新的 Page，並將其作為第一個位置參數
           注入被裝飾的函式。
        5. 函式執行完畢（無論成功或拋出例外）後，自動關閉 Context
           釋放頁面資源，但不關閉共用的 Browser 實體。

    使用方式：
        @open_playwright_page
        async def my_scraper(page: Page, url: str) -> str:
            await page.goto(url)
            return await page.title()

        # 呼叫時不需傳入 page 參數，裝飾器自動注入
        result = await my_scraper(url="https://example.com")

    Args:
        func (Callable): 被裝飾的非同步函式。其第一個參數必須為
                         `playwright.async_api.Page` 型別。

    Returns:
        Callable: 包裝後的非同步函式，簽名與原函式相同，但省略
                  第一個 `page` 參數（由裝飾器自動注入）。
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Optional[Any]:
        async with browser_pool._semaphore:
            browser = await browser_pool.get_browser()
            
            # 建立獨立 Context
            context = await browser.new_context(
                viewport=None,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York"
            )

            # 防偵測注入
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            page = await context.new_page()

            try:
                # 將 page 作為第一個參數傳入被裝飾的函式
                return await func(page, *args, **kwargs)
            finally:
                # 任務結束，只關閉 Context，不關閉 Browser
                await context.close()

    return wrapper


async def close_playwright():
    """
    釋放全域 BrowserPool 所持有的 Browser 與 Playwright 引擎資源。

    應在主程式的 `finally` 區塊中呼叫，確保無論執行成功或發生例外，
    Chromium 子行程都能被正確終止，避免殭屍行程殘留。

    範例：
        try:
            await main_scraping_logic()
        finally:
            await close_playwright()
    """
    await browser_pool.close()