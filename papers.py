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
# 解析 RSS/Atom，提取标题+摘要
# ==============================

def parse_rss(r, source, keywords, limit=10):
    papers = []
    try:
        root = ET.fromstring(r.text)

        # 兼容 RSS 2.0 和 Atom
        items = root.findall(".//item")
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall("atom:entry", ns)

        for item in items:
            # 标题
            title_el = item.find("title")
            if title_el is None or not title_el.text:
                continue
            title = title_el.text.strip()

            # 摘要：优先 description，其次 summary
            abstract = ""
            for tag in ["description", "summary", "{http://www.w3.org/2005/Atom}summary"]:
                el = item.find(tag)
                if el is not None and el.text and len(el.text.strip()) > 30:
                    soup = BeautifulSoup(el.text, "html.parser")
                    abstract = soup.get_text().strip()[:400]
                    break

            # 关键词过滤（标题或摘要）
            combined = (title + " " + abstract).lower()
            if not any(k.lower() in combined for k in keywords):
                continue

            papers.append({"title": title, "abstract": abstract or "（摘要获取失败）", "source": source})
            if len(papers) >= limit:
                break

    except Exception as e:
        print(f"[{source}] RSS解析失败：{e}")

    return papers

# ==============================
# 1. arXiv（econ + cs.AI/cs.CL）
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
# 2. NBER（用 repec.nber.org RSS）
# ==============================

def get_nber(keywords):
    print("[NBER] 开始抓取...")
    # NBER 通过 RePEC 提供的 RSS
    url = "https://nber.org/rss/new.xml"
    r = safe_get(url)
    if not r:
        # 备用：RePEC NBER feed
        url = "https://econpapers.repec.org/rss/nberwo.xml"
        r = safe_get(url)
    if not r:
        print("[NBER] 所有链接失败，跳过")
        return []
    papers = parse_rss(r, "NBER", keywords, limit=10)
    print(f"[NBER] 获取到 {len(papers)} 篇")
    return papers

# ==============================
# 3. NEP 专题 RSS（国际贸易、创新、AI经济）
#    来源：IDEAS/RePEC NEP 报告
# ==============================

def get_nep(keywords):
    print("[NEP] 开始抓取...")
    # NEP 各专题 RSS，直接对应你的研究方向
    feeds = [
        ("NEP-ITN", "https://nep.repec.org/nep-itn.rss"),   # 国际贸易
        ("NEP-INO", "https://nep.repec.org/nep-ino.rss"),   # 创新
        ("NEP-AIN", "https://nep.repec.org/nep-ain.rss"),   # AI经济
        ("NEP-TEC", "https://nep.repec.org/nep-tec.rss"),   # 技术与工业经济
        ("NEP-GVC", "https://nep.repec.org/nep-gth.rss"),   # 博弈论（含GVC）
    ]
    all_papers = []
    for name, url in feeds:
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
# 4. 顶刊：QJE / JPE / REStud / JIE
#    AER 无 RSS，用 OUP / Chicago RSS
# ==============================

def get_top_journals(keywords):
    print("[顶刊] 开始抓取...")
    feeds = [
        ("QJE",    "https://academic.oup.com/rss/site_5504/3365.xml"),
        ("JPE",    "https://www.journals.uchicago.edu/action/showFeed?type=etoc&feed=rss&jc=jpe"),
        ("REStud", "https://academic.oup.com/rss/site_5508/3369.xml"),
        ("JIE",    "https://rss.sciencedirect.com/publication/science/00221996"),  # Journal of International Economics
        ("JDE",    "https://rss.sciencedirect.com/publication/science/03043878"),  # Journal of Development Economics
    ]
    all_papers = []
    for name, url in feeds:
        try:
            r = safe_get(url)
            if not r:
                print(f"[{name}] 无法访问，跳过")
                continue
            papers = parse_rss(r, name, keywords, limit=10)
            print(f"[{name}] 获取到 {len(papers)} 篇")
            all_papers += papers
        except Exception as e:
            print(f"[{name}] 失败，跳过：{e}")
    return all_papers

# ==============================
# 汇总所有来源
# ==============================

def get_all_papers(keywords):
    all_papers = []
    all_papers += get_arxiv(keywords)
    all_papers += get_nber(keywords)
    all_papers += get_nep(keywords)
    all_papers += get_top_journals(keywords)

    # 去重（按标题）
    seen = set()
    unique = []
    for p in all_papers:
        if p["title"] not in seen:
            seen.add(p["title"])
            unique.append(p)

    sources = {p["source"] for p in unique}
    print(f"[汇总] 共找到相关论文 {len(unique)} 篇，来源：{sources}")
    return unique
