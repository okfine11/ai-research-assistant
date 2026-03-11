import requests
from bs4 import BeautifulSoup

def get_nber():

    url = "https://www.nber.org/papers"

    r = requests.get(url)

    soup = BeautifulSoup(r.text,"html.parser")

    papers = []

    for i in soup.select(".paper-card")[:5]:

        title = i.select_one(".title").text.strip()

        papers.append(title)

    return papers
