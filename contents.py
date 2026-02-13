from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.exceptions import Timeout, ConnectionError, ProxyError, RequestException
import time
import csv
import pandas as pd
from tqdm import tqdm

class BlogContentBot:
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
  
            print("登录成功，Cookie 已提取")
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
            print("文章目录读取成功")
            return lines  

        except FileNotFoundError:
            return []

    def blog_article_api(self, article_url, writer=None):
        """
        核心爬取请求
        返回: (是否成功, url, 是否需要重试)
        """
        target_id = article_url.rstrip('/').split('/')[-1]
        target_url = f"{self.base_url}/blog/spider/blogs/{target_id}"
        headers = {"Referer": article_url}
  
        try:
            response = self.session.get(target_url, headers=headers, timeout=20)
            if response.status_code == 200:
                data = response.json()
                if data:
                    blog_id = target_id
                    blog_title = data["meta"]["title"]
                    blog_author = data["meta"]["author"]
                    blog_content = data["meta"]["content"]
                    blog_date = data["meta"]["date"]
                    if writer:
                        writer.writerow([blog_author, blog_id, blog_title, blog_content, blog_date])
                    return True, article_url, False
                else:
                    return False, article_url, False # 数据为空，不重试
            elif response.status_code in [500, 502, 503, 504]:
                return False, article_url, True # 服务器错误，重试
            else:
                return False, article_url, False # 403/404 等，不重试

        except (Timeout, ConnectionError, ProxyError):
            return False, article_url, True # 网络错误，重试
        except RequestException:
            return False, article_url, False # 其它错误，不重试

    def csv_process(self, filename):
        '''csv尾处理'''
        try:
            df = pd.read_csv(filename, encoding='utf-8-sig')
            df = df.sort_values(by="文章作者", ascending=True)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print("文章内容爬取完毕")
            return True

        except FileNotFoundError:
            print("未找到博客文章")
            return False

    def run(self):
        '''主运行函数'''
        start_time = time.time()
        print("欢迎使用yaozi开发的博客爬取机器人！\n")
  
        # 登录，获取Cookies
        if not self.login_and_get_cookies():
            return

        # 读取文章目录
        pending_articles = self.load_articles_from_file()
        total_initial = len(pending_articles)
        if total_initial == 0: 
            print("没有读取到文章目录")
            return
        
        # 博客内容爬取
        max_rounds = 5  # 最大清洗轮数
        success_total = 0
        filename = "article_details.csv"

        with open(filename, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['文章作者', '文章id', '文章标题', '文章内容', '发布日期'])   

            for round_idx in range(1, max_rounds + 1):
                if not pending_articles:
                    break

                current_total = len(pending_articles)
                retry_list = [] 
                round_success = 0
                round_fail = 0
                print(f"第 {round_idx}/{max_rounds} 轮清洗开始 (待处理: {current_total}) ---")
  
                # 开启线程池，进行内容爬取
                with ThreadPoolExecutor(max_workers = 5) as executor:
                    future_to_url = {executor.submit(self.blog_article_api, url, writer): url for url in pending_articles}
                    pbar = tqdm(total=current_total, unit='篇', desc=f'第{round_idx}轮', ncols=100, colour='green')
                    for future in as_completed(future_to_url):
                        is_success, url, should_retry = future.result()
                        if is_success:
                            success_total += 1
                            round_success += 1
                        else:
                            round_fail += 1
                            if should_retry:
                                retry_list.append(url)
                        pbar.update(1)
                        pbar.set_postfix(成功=round_success, 失败=round_fail, 待重试=len(retry_list))
                    pbar.close()

                # 更新待处理列表
                pending_articles = retry_list
                if pending_articles:
                    time.sleep(1)

        # 尾处理
        if not self.csv_process(filename):
            return

        # 计算耗时
        end_time = time.time()
        total_time = end_time - start_time

        # 最终报告
        print("最终任务报告")
        print(f"总文章数 : {total_initial}")
        print(f"成功爬取 : {success_total}")
        print(f"成功率 : {success_total / total_initial:.2%}")
        print(f"耗时 : {total_time:.2f} 秒")
  
        # 失败文章导出
        if pending_articles:
            print(f"有 {len(pending_articles)} 篇失败，已保存至 failed_urls.txt")
            with open("failed_urls.txt", "w", encoding="utf-8-sig") as f:
                for url in pending_articles:
                    f.write(url + "\n")
        else:
            print("所有文章处理完毕！")

if __name__ == "__main__":
    bot = BlogContentBot(
        base_url="base_url",
        username="username",
        password="password",
    )
    bot.run()