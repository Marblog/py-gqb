import os
import re
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "https://www.gequbao.com/top/week-download?page={}"
SAVE_DIR = "D:/python/songs/week-top"
PAGES = 1  # 这里测试1页，改成页码即可

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)


def cookies_from_driver(driver):
    cookies = driver.get_cookies()
    cookie_dict = {}
    for cookie in cookies:
        cookie_dict[cookie['name']] = cookie['value']
    return cookie_dict


def send_ad_handle(session, song_url, headers):
    api_url = "https://www.gequbao.com/api/ad-handle"
    post_headers = headers.copy()
    post_headers.update({
        'origin': 'https://www.gequbao.com',
        'referer': song_url,
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'x-requested-with': 'XMLHttpRequest',
    })
    # 观察接口请求体似乎是空字符串
    data = ""
    resp = session.post(api_url, headers=post_headers, data=data)
    if resp.status_code == 200 and resp.json().get('code') == 1:
        print(f"广告接口调用成功")
        return True
    else:
        print(f"广告接口调用失败: {resp.text}")
        return False


def download_file_with_cookies(url, path, session):
    with session.get(url, stream=True) as r:
        r.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)


def download_song(driver, session, song_url, song_title, save_dir):
    song_title = clean_filename(song_title)
    os.makedirs(save_dir, exist_ok=True)

    driver.get(song_url)
    wait = WebDriverWait(driver, 20)

    try:
        # 先调用广告接口
        cookies = cookies_from_driver(driver)
        session.cookies.update(cookies)
        if not send_ad_handle(session, song_url, HEADERS):
            print(f"❌ {song_title} 广告接口调用失败，跳过")
            return

        # 找到下载按钮，点击弹窗
        mp3_btn = wait.until(EC.element_to_be_clickable((By.ID, "btn-download-mp3")))
        driver.execute_script("arguments[0].scrollIntoView();", mp3_btn)
        mp3_btn.click()

        # 等待弹窗出现
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.jconfirm-box")))
        time.sleep(2)  # 等待弹窗内容渲染

        # 找到低品质链接，点击触发真实链接
        low_quality_link = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.jconfirm-box a.default-link"))
        )
        low_quality_link.click()
        time.sleep(2)

        # selenium切换到新标签页拿真实mp3地址
        handles = driver.window_handles
        if len(handles) > 1:
            driver.switch_to.window(handles[-1])
            mp3_url = driver.current_url
            driver.close()
            driver.switch_to.window(handles[0])
        else:
            mp3_url = low_quality_link.get_attribute("href")

        if not mp3_url or mp3_url in ('about:blank', ''):
            print(f"❌ {song_title} 未获得有效下载链接，跳过")
            return

        mp3_path = os.path.join(save_dir, f"{song_title}.mp3")
        print(f"开始下载低品质MP3: {song_title} -> {mp3_url}")
        download_file_with_cookies(mp3_url, mp3_path, session)
        print(f"✅ {song_title} 低品质MP3下载完成")

        # 关闭弹窗
        close_btn = driver.find_element(By.CSS_SELECTOR, "div.jconfirm-closeIcon")
        close_btn.click()
        time.sleep(1)

    except Exception as e:
        print(f"❌ {song_title} 下载失败: {e}")


def main():
    options = Options()
    options.add_argument('--headless')  # 你想看到浏览器界面调试时可以注释掉
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("user-agent=" + HEADERS['User-Agent'])

    driver = webdriver.Chrome(options=options)
    session = requests.Session()
    session.headers.update(HEADERS)

    for page in range(1, PAGES + 1):
        print(f"\n===== 正在处理第 {page} 页 =====")
        url = BASE_URL.format(page)
        res = requests.get(url, headers=HEADERS)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        table_div = soup.find('div', class_='table-responsive')
        if not table_div:
            print("⚠️ 没找到歌曲列表，可能页面结构变了")
            continue

        links = table_div.find_all('a')
        print(f"本页找到 {len(links)} 首歌")

        for a in links:
            href = a.get('href')
            if not href:
                continue
            song_url = 'https://www.gequbao.com' + href
            song_title = a.text.strip()
            try:
                download_song(driver, session, song_url, song_title, SAVE_DIR)
            except Exception as e:
                print(f"❌ {song_title} 下载异常: {e}")
            time.sleep(2)  # 控制节奏，避免请求过快

    driver.quit()
    print("\n全部下载完成！")


if __name__ == '__main__':
    main()

