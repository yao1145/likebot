import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import Timeout, ConnectionError, ProxyError, RequestException
import time
import pandas as pd
from tqdm import tqdm

class BlogLikeClickBot:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def login_and_get_cookies(self):
        """Selenium 登录并获取 Cookie"""
        print("正在启动浏览器进行登录...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless") 
        options.add_argument("--disable-gpu")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 10)

        try:
            driver.get(f"{self.base_url}/auth/login")

            wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(self.username)
            driver.find_element(By.ID, "password").send_keys(self.password)
            driver.find_element(By.ID, "submitBtn").click()
            wait.until(EC.url_contains("/"))
            time.sleep(1) 
        
            selenium_cookies = driver.get_cookies()
            for cookie in selenium_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
        
            print("登录成功，Cookie 已提取。\n")
            return True
        except Exception as e:
            print(f"登录失败: {e}")
            return False
        finally:
            driver.quit()

    def load_articles_from_file(self, filename="admin_articles.csv"):
        """从文件加载文章 URL"""
        try:
            lines = []
            df = pd.read_csv(filename)
            for i in df.index:
                lines.append(df["文章链接"][i])
            return lines          

        except FileNotFoundError:
            return []

    def like_article_api(self, article_url):
        """
        核心点赞请求
        返回: (是否成功, url, 是否需要重试)
        """
        article_url = article_url.rstrip('/')
        target_url = f"{article_url}/like"
        headers = {"Referer": article_url}
    
        try:
            # 设置较短的超时，配合多轮清洗
            response = self.session.post(target_url, headers=headers, timeout=5)
            if response.status_code == 200:
                return True, article_url, False
            elif response.status_code in [500, 502, 503, 504]:
                return False, article_url, True # 服务器错误，重试
            else:
                return False, article_url, False # 403/404 等，不重试

        except (Timeout, ConnectionError, ProxyError):
            return False, article_url, True # 网络错误，重试
        except RequestException:
            return False, article_url, False

    def run(self):
        '''主运行函数'''
        start_time = time.time()
        
        # 登录，获取Cookies
        if not self.login_and_get_cookies():
            return

        # 读取文章目录
        pending_articles = self.load_articles_from_file()
        total_initial = len(pending_articles)
        if total_initial == 0: 
            print("没有读取到文章。")
            return

        max_rounds = 5  # 最大清洗轮数
        success_total = 0
    
        # 多轮清洗循环
        for round_idx in range(1, max_rounds + 1):
            if not pending_articles:
                break 
        
            current_total = len(pending_articles)
            retry_list = [] 
        
            # 本轮统计
            round_success = 0
            round_fail = 0
            print(f"第 {round_idx}/{max_rounds} 轮清洗开始 (待处理: {current_total}) ---")
        
            # 开启线程池
            with ThreadPoolExecutor(max_workers = 20) as executor:
                # 提交任务
                future_to_url = {executor.submit(self.like_article_api, url): url for url in pending_articles}
                with tqdm(total=current_total, unit='篇', desc='进度', ncols=100, colour='green') as pbar: 
                    for future in as_completed(future_to_url):
                        is_success, url, should_retry = future.result()
                        if is_success:
                            success_total += 1
                            round_success += 1
                        else:
                            round_fail += 1
                            if should_retry:
                                retry_list.append(url)
                    
                        # 更新进度条
                        pbar.update(1)
                        pbar.set_postfix(成功=round_success, 失败=round_fail, 待重试=len(retry_list))

            # 更新待处理列表
            pending_articles = retry_list
            if pending_articles:
                time.sleep(1)
            
        # 计算耗时
        end_time = time.time()
        total_time = end_time - start_time

        # 最终报告
        print(f" 最终任务报告")
        print(f" 总文章数 : {total_initial}")
        print(f" 成功点赞 : {success_total}")
        print(f" 成功率 : {success_total / total_initial:.2%}")
        print(f" 耗时 : {total_time:.2f} 秒")
    
        # 失败文章导出
        if pending_articles:
            print(f" 有 {len(pending_articles)} 篇失败，已保存至 failed_urls.txt")
            with open("failed_urls.txt", "w", encoding="utf-8") as f:
                for url in pending_articles:
                    f.write(url + "\n")
        else:
            print(" 所有文章处理完毕！")

if __name__ == "__main__":
    bot = BlogLikeClickBot(
        base_url="base_url",
        username="username",
        password="password",
    )
    bot.run()