# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup as bs
import urllib.request
import re

url = 'http://www.52dsm.com/chapter/6712.html'
# url = 'http://www.piaotian.net/html/5/5924/'
webstory = urllib.request.urlopen(url)
s = webstory.read()

soup = bs(s, 'html5lib')

content = soup.find_all(id="content")
if len(content) == 0:
    content = soup.find_all(id='chapterlist')
if len(content) == 0:
    content = soup.find('div', re.compile('centent|mainbody|catalog.box'))
contentbs = bs(str(content), 'html5lib')

urllist = contentbs.find_all('a')

def get_href(zhangjie_tag):
    page_rul = []
    for index in zhangjie_tag:
        url = index.get('href')
        title = index.get_text()
        if re.match('^javascript:[^content]+|/?class', url):
            continue
        page_rul.append([url, title])
    return page_rul
url_list = get_href(urllist)
for x in url_list:
    print(x)
print(len(url_list))