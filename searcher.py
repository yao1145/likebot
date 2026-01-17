from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import pandas as pd
from tqdm import tqdm

class BlogSearchBot:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.driver = webdriver.Chrome() 
        self.wait = WebDriverWait(self.driver, 10)
  
    def login(self):
        """登录网站"""
        try:
            self.driver.get(f"{self.base_url}/auth/login")
            username_input = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            password_input = self.driver.find_element(By.ID, "password")
            username_input.send_keys(self.username)
            password_input.send_keys(self.password)
            login_button = self.driver.find_element(By.ID, "submitBtn")
            login_button.click()
            self.wait.until(EC.url_contains("/"))
            print("登录成功！")
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
        """查找文章（已添加进度条）"""
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")

            # 寻找博客文章    
            articles = []
            elements = self.driver.find_elements(By.TAG_NAME, "article")
            if elements:
                articles = elements
                print(f"找到 {len(articles)} 个文章元素")
            else:
                print(f"未找到文章")
        
            # 处理找到的文章
            print(f"\n开始处理 {len(articles)} 篇文章...")
            admin_articles = []
            for i, article in enumerate(tqdm(articles, desc="正在解析文章", unit="篇")):
                try:
                    # 寻找文章作者
                    author = None
                    author_element = article.find_element(By.CSS_SELECTOR, "[class*='author']")
                    author = author_element.text.strip()
                  
                    # 处理作者格式
                    if author:
                        author = author_element.text.strip().split('\n')[0]
                        link = article.find_element(By.TAG_NAME, "a")
                        url = link.get_attribute("href")
                        admin_articles.append([author, url])
                    
                except Exception as e:
                    tqdm.write(f" 处理文章 {i+1} 时出错: {e}")
                    continue
        
            print(f"\n最终找到 {len(admin_articles)} 篇文章")
            return admin_articles
        
        except Exception as e:
            print(f"查找文章时出错: {e}")
            import traceback
            traceback.print_exc()
            return []

    def save_articles_to_file(self, articles, filename="admin_articles.csv"):
        """保存为csv文件"""
        try:
            df = pd.DataFrame(articles, columns=['作者', '文章链接'])
            df = df.sort_values(by='作者', ascending=True)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"已保存 {len(articles)} 篇文章到 {filename}")
            return True
        except Exception as e:
            print(f"保存失败: {e}")
            return False

    def run(self):
        """执行完整流程"""
        try:
            if not self.login(): return
            if not self.navigate_to_blog(): return
            admin_articles = self.find_admin_articles()
            self.save_articles_to_file(admin_articles)
        finally:
            time.sleep(3)
            self.driver.quit()

if __name__ == "__main__":
    bot = BlogSearchBot(
        base_url="http://116.62.179.232:22822",
        username="H4C3O4",
        password="h4c3o4",
    )
    bot.run()