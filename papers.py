import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

# ==============================
# 所有 RSS 链接（集中管理，方便维护）
# ==============================

NEP_FEEDS = [
    ("NEP-INT", "https://nep.repec.org/nep-int.rss.xml"),   # 国际贸易
    ("NEP-INO", "https://nep.repec.org/nep-ino.rss.xml"),   # 创新
    ("NEP-AIN", "https://nep.repec.org/nep-ain.rss.xml"),   # AI经济
    ("NEP-IPR", "https://nep.repec.org/nep-ipr.rss.xml"),   # 知识产权
    ("NEP-TEC", "https://nep.repec.org/nep-tid.rss.xml"),   # 技术与工业发展
    ("NEP-CNA", "https://nep.repec.org/nep-cna.rss.xml"),   # 中国经济
]

JOURNAL_FEEDS = [
    ("QJE",    "https://academic.oup.com/rss/site_5504/3365.xml"),
    ("JPE",    "https://www.journals.uchicago.edu/action/showFeed?type=etoc&feed=rss&jc=jpe"),
    ("REStud", "https://academic.oup.com/rss/site_5508/3369.xml"),
    ("JIE",    "https://rss.sciencedirect.com/publication/science/00221996"),
    ("JDE",    "https://rss.sciencedirect.com/publication/science/03043878"),
]

# 供健康检查使用
ALL_FEEDS = (
    [("NBER_RSS", "https://econpapers.repec.org/rss/nberwo.xml")]
    + NEP_FEEDS
    + JOURNAL_FEEDS
)

# ==============================
# 工具：安全请求
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
# 解析 RSS，提取标题+摘要
# keywords=None 表示不过滤（顶刊全量返回，由AI来判断）
# ==============================

def parse_rss(r, source, keywords=None, limit=10):
    papers = []
    try:
        root = ET.fromstring(r.text)
        items = root.findall(".//item")
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall("atom:entry", ns)

        for item in items:
            title_el = item.find("title")
            if title_el is None or not title_el.text:
                continue
            title = title_el.text.strip()

            # 摘要
            abstract = ""
            for tag in ["description", "summary"]:
                el = item.find(tag)
                if el is not None and el.text and len(el.text.strip()) > 30:
                    soup = BeautifulSoup(el.text, "html.parser")
                    abstract = soup.get_text().strip()[:400]
                    break

            # 关键词过滤（None = 不过滤）
            if keywords is not None:
                combined = (title + " " + abstract).lower()
                if not any(k.lower() in combined for k in keywords):
                    continue

            papers.append({
                "title": title,
                "abstract": abstract or "（摘要获取失败）",
                "source": source
            })
            if len(papers) >= limit:
                break

    except Exception as e:
        print(f"[{source}] RSS解析失败：{e}")

    return papers

# ==============================
# 1. arXiv
# ==============================

def get_arxiv(keywords):
    print("[arXiv] 开始抓取...")
    try:
        kw_query = "+OR+".join([f'ti:"{k}"' for k in keywords[:8]])
        url = f"https://export.arxiv.org/api/query?search_query={kw_query}&sortBy=submittedDate&sortOrder=descending&max_results=30"
        r = safe_get(url)
        if not r:
            return []

        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []

        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            abs_el   = entry.find("atom:summary", ns)
            if title_el is None:
                continue
            title    = title_el.text.strip().replace("\n", " ")
            abstract = abs_el.text.strip().replace("\n", " ")[:400] if abs_el is not None else ""
            papers.append({"title": title, "abstract": abstract, "source": "arXiv"})
            if len(papers) >= 10:
                break

        print(f"[arXiv] 获取到 {len(papers)} 篇")
        return papers
    except Exception as e:
        print(f"[arXiv] 失败，跳过：{e}")
        return []

# ==============================
# 2. NBER
# ==============================

def get_nber(keywords):
    print("[NBER] 开始抓取...")
    url = "https://econpapers.repec.org/rss/nberwo.xml"
    r = safe_get(url)
    if not r:
        print("[NBER] 失败，跳过")
        return []
    papers = parse_rss(r, "NBER", keywords, limit=10)
    print(f"[NBER] 获取到 {len(papers)} 篇")
    return papers

# ==============================
# 3. NEP 专题（关键词过滤）
# ==============================

def get_nep(keywords):
    print("[NEP] 开始抓取...")
    all_papers = []
    for name, url in NEP_FEEDS:
        try:
            r = safe_get(url)
            if not r:
                continue
            papers = parse_rss(r, name, keywords, limit=10)
            print(f"[{name}] 获取到 {len(papers)} 篇")
            all_papers += papers
        except Exception as e:
            print(f"[{name}] 失败，跳过：{e}")
    return all_papers

# ==============================
# 4. 顶刊（不过滤关键词，全量返回交给AI判断）
# ==============================

def get_top_journals():
    print("[顶刊] 开始抓取...")
    all_papers = []
    for name, url in JOURNAL_FEEDS:
        try:
            r = safe_get(url)
            if not r:
                print(f"[{name}] 无法访问，跳过")
                continue
            # 顶刊不做关键词过滤，取最新10篇交给AI筛选
            papers = parse_rss(r, name, keywords=None, limit=10)
            print(f"[{name}] 获取到 {len(papers)} 篇")
            all_papers += papers
        except Exception as e:
            print(f"[{name}] 失败，跳过：{e}")
    return all_papers

# ==============================
# 汇总
# ==============================

def get_all_papers(keywords):
    all_papers = []
    all_papers += get_arxiv(keywords)
    all_papers += get_nber(keywords)
    all_papers += get_nep(keywords)
    all_papers += get_top_journals()   # 顶刊不传keywords，全量给AI

    # 去重
    seen = set()
    unique = []
    for p in all_papers:
        if p["title"] not in seen:
            seen.add(p["title"])
            unique.append(p)

    sources = {p["source"] for p in unique}
    print(f"[汇总] 共找到论文 {len(unique)} 篇，来源：{sources}")
    return unique
