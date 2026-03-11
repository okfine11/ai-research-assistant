import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

# ==============================
# 工具：安全请求，失败返回 None
# ==============================

def safe_get(url, timeout=8):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r
        print(f"[跳过] {url} 返回 {r.status_code}")
        return None
    except Exception as e:
        print(f"[跳过] {url} 请求失败：{e}")
        return None

# ==============================
# 1. arXiv（每次最多3篇）
# ==============================

def get_arxiv(keywords):
    print("[arXiv] 开始抓取...")
    try:
        kw_query = "+OR+".join([f'ti:"{k}"' for k in keywords[:6]])
        url = f"https://export.arxiv.org/api/query?search_query={kw_query}&sortBy=submittedDate&sortOrder=descending&max_results=20"
        r = safe_get(url)
        if not r:
            return []

        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []

        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            abstract = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
            abstract = abstract[:300] + "..." if len(abstract) > 300 else abstract
            papers.append({"title": title, "abstract": abstract, "source": "arXiv"})
            if len(papers) >= 10:  # 每个来源最多3篇
                break

        print(f"[arXiv] 获取到 {len(papers)} 篇")
        return papers

    except Exception as e:
        print(f"[arXiv] 失败，跳过：{e}")
        return []

# ==============================
# 2. NBER（用 RSS 更稳定，每次最多3篇）
# ==============================

def get_nber(keywords):
    print("[NBER] 开始抓取...")
    try:
        # 用 NBER RSS 代替抓 HTML，更稳定
        r = safe_get("https://www.nber.org/rss/new_working_papers.xml")
        if not r:
            return []

        root = ET.fromstring(r.text)
        papers = []

        for item in root.findall(".//item"):
            title_el = item.find("title")
            desc_el  = item.find("description")
            if title_el is None or not title_el.text:
                continue

            title = title_el.text.strip()

            # 关键词过滤
            if not any(k.lower() in title.lower() for k in keywords):
                continue

            # 摘要从 description 取
            abstract = ""
            if desc_el is not None and desc_el.text:
                soup = BeautifulSoup(desc_el.text, "html.parser")
                abstract = soup.get_text().strip()[:300] + "..."

            papers.append({"title": title, "abstract": abstract or "（摘要获取失败）", "source": "NBER"})
            if len(papers) >= 10:
                break

        print(f"[NBER] 获取到 {len(papers)} 篇")
        return papers

    except Exception as e:
        print(f"[NBER] 失败，跳过：{e}")
        return []

# ==============================
# 3. 四大顶刊 RSS（每刊最多2篇，共最多8篇）
# ==============================

def get_top_journals(keywords):
    print("[顶刊] 开始抓取...")

    feeds = [
        ("AER",    "https://www.aeaweb.org/journals/aer/issues/rss"),
        ("QJE",    "https://academic.oup.com/rss/site_5504/3365.xml"),
        ("JPE",    "https://www.journals.uchicago.edu/action/showFeed?type=etoc&feed=rss&jc=jpe"),
        ("REStud", "https://academic.oup.com/rss/site_5508/3369.xml"),
    ]

    papers = []

    for name, url in feeds:
        try:
            r = safe_get(url, timeout=8)
            if not r:
                print(f"[{name}] 无法访问，跳过")
                continue

            root = ET.fromstring(r.text)
            count = 0

            for item in root.findall(".//item"):
                title_el = item.find("title")
                if title_el is None or not title_el.text:
                    continue
                title = title_el.text.strip()

                # 关键词过滤（顶刊论文标题不一定含关键词，放宽匹配）
                title_lower = title.lower()
                matched = any(k.lower() in title_lower for k in keywords)

                # 如果标题匹配不上，尝试从 description 里匹配
                if not matched:
                    desc_el = item.find("description")
                    if desc_el is not None and desc_el.text:
                        desc_lower = desc_el.text.lower()
                        matched = any(k.lower() in desc_lower for k in keywords)

                if not matched:
                    continue

                # 摘要
                abstract = ""
                desc_el = item.find("description")
                if desc_el is not None and desc_el.text:
                    soup = BeautifulSoup(desc_el.text, "html.parser")
                    abstract = soup.get_text().strip()[:300] + "..."

                papers.append({"title": title, "abstract": abstract or "（摘要获取失败）", "source": name})
                count += 1
                if count >= 10:  # 每个刊最多2篇
                    break

            print(f"[{name}] 获取到 {count} 篇")

        except Exception as e:
            print(f"[{name}] 失败，跳过：{e}")
            continue

    return papers

# ==============================
# 汇总所有来源
# ==============================

def get_all_papers(keywords):
    all_papers = []
    all_papers += get_arxiv(keywords)
    all_papers += get_nber(keywords)
    all_papers += get_top_journals(keywords)

    # 去重
    seen = set()
    unique = []
    for p in all_papers:
        if p["title"] not in seen:
            seen.add(p["title"])
            unique.append(p)

    print(f"[汇总] 共找到相关论文 {len(unique)} 篇，来源：{ {p['source'] for p in unique} }")
    return unique
