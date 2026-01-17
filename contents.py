from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options  # 用于设置无头模式
import time
import pandas as pd
import csv  # 用于实时写入
from tqdm import tqdm

class BlogSearchBot:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        # 初始化普通有头浏览器
        self.driver = webdriver.Chrome() 
        self.wait = WebDriverWait(self.driver, 10)
        self.cookies = [] # 用于存储登录后的cookie
  
    def login(self):
        """登录网站并保存Cookie"""
        try:
            self.driver.get(f"{self.base_url}/auth/login")
        
            username_input = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            password_input = self.driver.find_element(By.ID, "password")
            username_input.send_keys(self.username)
            password_input.send_keys(self.password)
            login_button = self.driver.find_element(By.ID, "submitBtn")
            login_button.click()
        
            self.wait.until(EC.url_contains("/"))
            print("登录成功！保存Cookies...")
            # 【新增】保存登录后的Cookie
            self.cookies = self.driver.get_cookies()
            return True

        except TimeoutException:
            print("登录失败或超时")
            return False
  
    def navigate_to_blog(self):
        """导航到博客区"""
        try:
            time.sleep(2)
            blog_link = self.wait.until(
                EC.element_to_be_clickable((By.LINK_TEXT, "博客"))
            )
            blog_link.click()
            self.wait.until(EC.url_contains("/blog"))
            print("成功进入博客区!")
            return True
        except TimeoutException:
            print("无法进入博客区")
            return False
  
    def find_admin_articles(self):
        """查找文章列表"""
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")

            articles = []
            elements = self.driver.find_elements(By.TAG_NAME, "article")
            if elements:
                articles = elements
                print(f"找到 {len(articles)} 个文章元素")
            else:
                print(f"未找到文章")
        
            print(f"\n开始解析列表...")
            admin_articles = []
        
            # 解析列表数据
            for i, article in enumerate(tqdm(articles, desc="解析列表", unit="篇")):
                try:
                    author_element = article.find_element(By.CSS_SELECTOR, "[class*='author']")
                    author = author_element.text.strip().split('\n')[0]
                    link = article.find_element(By.TAG_NAME, "a")
                    url = link.get_attribute("href")
                    admin_articles.append({'author': author, 'url': url})
                except Exception as e:
                    tqdm.write(f"解析文章 {i+1} 失败: {e}")
                    continue
            
            return admin_articles
        
        except Exception as e:
            print(f"查找文章时出错: {e}")
            return []

    def save_list_to_csv(self, articles_data, filename="admin_articles.csv"):
        """保存初步列表"""
        try:
            df = pd.DataFrame(articles_data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"文章列表已保存到 {filename}")
        except Exception as e:
            print(f"列表保存失败: {e}")

    def switch_to_headless(self):
        """【新增】切换到无头浏览器模式并注入Cookie"""
        print("\n正在切换到无头浏览器模式(Headless Mode)...")
        
        # 1. 关闭旧的有头浏览器
        self.driver.quit()

        # 2. 配置无头模式
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 开启无头
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        # 某些网站可能需要模拟User-Agent防止反爬
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        # 1. 页面加载策略：eager 
        # (DOM加载完就返回，不等待图片、CSS加载完成，速度显著提升)
        chrome_options.page_load_strategy = 'eager' 

        # 2. 禁止加载图片和 CSS
        prefs = {
            "profile.managed_default_content_settings.images": 2, # 禁止图片
            "profile.managed_default_content_settings.stylesheets": 2, # 禁止CSS (慎用，有时会影响内容定位)
        }
        chrome_options.add_experimental_option("prefs", prefs)        
        
        # 3. 启动新浏览器
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10) # 更新 wait 对象

        # 4. 注入Cookie (需要先访问同一个域名的页面才能设置Cookie)
        try:
            # 先访问登录页或首页，建立域名上下文
            self.driver.get(f"{self.base_url}/auth/login") 
            
            # 删除旧Cookie并添加之前保存的登录Cookie
            self.driver.delete_all_cookies()
            for cookie in self.cookies:
                self.driver.add_cookie(cookie)
            
            print("Cookie注入完成，准备抓取详情...")
        except Exception as e:
            print(f"Cookie注入失败: {e}")

    def scrape_details_realtime(self, articles_data, filename="article_details.csv"):
        """【新增】访问详情页并实时写入CSV"""
        print(f"开始抓取详情内容，目标文件: {filename}")
        
        # 使用 'w' 模式打开文件，newline='' 防止空行
        # buffering=1 表示行缓冲（虽然csv模块自己管理，但加上是个好习惯）
        with open(filename, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow(['作者', '文章链接', '文章标题', '文章内容'])
            
            # 遍历文章列表
            for item in tqdm(articles_data, desc="抓取内容", unit="页"):
                url = item['url']
                author = item['author']
                title = "未获取"
                content = "未获取"

                try:
                    self.driver.get(url)
                    
                    try:
                        title_elem = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
                        title = title_elem.text.strip()
                    except:
                        title = "无标题"

                    try:
                        content_elem = self.driver.find_element(By.ID, "userContentContainer")
                        content = content_elem.text.strip()
                        
                        # 如果内容太长，为了CSV可读性，可以选择只截取前500字，或者保留全部
                    except NoSuchElementException:
                        content = "未找到正文内容"

                except Exception as e:
                    tqdm.write(f"访问 {url} 失败: {e}")
                
                # 【关键】实时写入一行
                writer.writerow([author, url, title, content])
                
                # 稍微休眠一下，避免请求过快被封
                time.sleep(0.5)

        print(f"\n所有内容抓取完成！已保存至 {filename}")

    def run(self):
        """执行完整流程"""
        try:
            # 1. 登录 (GUI模式)
            if not self.login(): return
        
            # 2. 进入列表 (GUI模式)
            if not self.navigate_to_blog(): return
        
            # 3. 获取链接列表 (GUI模式)
            articles_data = self.find_admin_articles()
            if not articles_data:
                print("未找到任何文章，程序结束。")
                return

            # 4. 保存链接列表到文件
            self.save_list_to_csv(articles_data)

            # 5. 切换到无头模式 (为了效率和静默运行)
            self.switch_to_headless()

            # 6. 遍历链接，爬取内容并实时写入
            self.scrape_details_realtime(articles_data)
        
        finally:
            # 关闭浏览器
            print("正在清理资源...")
            time.sleep(2)
            self.driver.quit()

if __name__ == "__main__":
    bot = BlogSearchBot(
        base_url="http://116.62.179.232:22822", # 请替换为实际地址
        username="H4C3O4",
        password="h4c3o4",
    )
    bot.run()