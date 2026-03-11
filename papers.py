import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

# ==============================
# 工具：安全请求，失败返回 None
# ==============================

def safe_get(url, timeout=15):
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
# 1. arXiv（含摘要，API 直接返回）
# ==============================

def get_arxiv(keywords):
    print("[arXiv] 开始抓取...")
    try:
        kw_query = "+OR+".join([f'ti:"{k}"' for k in keywords[:6]])
        url = f"https://export.arxiv.org/api/query?search_query={kw_query}&sortBy=submittedDate&sortOrder=descending&max_results=15"
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
            papers.append({
                "title": title,
                "abstract": abstract,
                "source": "arXiv"
            })

        print(f"[arXiv] 获取到 {len(papers)} 篇（含摘要）")
        return papers

    except Exception as e:
        print(f"[arXiv] 失败，跳过：{e}")
        return []

# ==============================
# 2. NBER（含摘要，详情页抓取）
# ==============================

def get_nber(keywords):
    print("[NBER] 开始抓取...")
    try:
        r = safe_get("https://www.nber.org/papers")
        if not r:
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        papers = []

        for card in soup.select(".paper-card")[:20]:
            title_el = card.select_one(".title")
            if not title_el:
                continue
            title = title_el.text.strip()

            if not any(k.lower() in title.lower() for k in keywords):
                continue

            # 抓摘要详情页
            link_el = title_el.find("a") or card.find("a", href=True)
            abstract = ""
            if link_el and link_el.get("href"):
                detail_url = "https://www.nber.org" + link_el["href"]
                detail = safe_get(detail_url, timeout=10)
                if detail:
                    detail_soup = BeautifulSoup(detail.text, "html.parser")
                    abs_el = detail_soup.select_one(".abstract, .paper-abstract, #abstract")
                    if abs_el:
                        abstract = abs_el.text.strip()[:300] + "..."
                time.sleep(0.5)

            papers.append({
                "title": title,
                "abstract": abstract if abstract else "（摘要获取失败）",
                "source": "NBER"
            })

            if len(papers) >= 5:
                break

        print(f"[NBER] 获取到 {len(papers)} 篇（含摘要）")
        return papers

    except Exception as e:
        print(f"[NBER] 失败，跳过：{e}")
        return []

# ==============================
# 3. 四大顶刊 RSS（含摘要）
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
            r = safe_get(url, timeout=15)
            if not r:
                continue

            root = ET.fromstring(r.text)

            for item in root.findall(".//item")[:15]:
                title_el = item.find("title")
                if title_el is None or not title_el.text:
                    continue
                title = title_el.text.strip()

                if not any(k.lower() in title.lower() for k in keywords):
                    continue

                # 从 <description> 取摘要
                abstract = ""
                desc_el = item.find("description")
                if desc_el is not None and desc_el.text:
                    desc_soup = BeautifulSoup(desc_el.text, "html.parser")
                    abstract = desc_soup.get_text().strip()[:300] + "..."

                # description 没有则抓详情页
                if not abstract or len(abstract) < 30:
                    link_el = item.find("link")
                    if link_el is not None and link_el.text:
                        detail = safe_get(link_el.text.strip(), timeout=10)
                        if detail:
                            ds = BeautifulSoup(detail.text, "html.parser")
                            abs_el = ds.select_one(".abstract, #abstract, .article-abstract")
                            if abs_el:
                                abstract = abs_el.get_text().strip()[:300] + "..."
                        time.sleep(0.5)

                papers.append({
                    "title": title,
                    "abstract": abstract if abstract else "（摘要获取失败）",
                    "source": name
                })

            print(f"[{name}] 获取到相关论文 {sum(1 for p in papers if p['source']==name)} 篇")

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

    print(f"[汇总] 共找到相关论文 {len(unique)} 篇")
    return unique[:12]
