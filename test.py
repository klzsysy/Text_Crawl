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

def special_treatment(raw):
    if re.match('javascript:content', raw):
        url_end = url.split('/')[-1].split('.')
        n1 = re.findall('\d+', raw)
        return '/{}/{}/{}{}'.format(n1[1], url_end[0], n1[0], '.' + url_end[1])
    return raw

def get_href(zhangjie_tag):
    page_rul = []
    for index in zhangjie_tag:
        raw = index.get('href')
        title = index.get_text()
        if re.match('^javascript:[^content]+|/?class', raw):
            continue
        page_rul.append([special_treatment(raw), title])
    return page_rul
url_list = get_href(urllist)
for x in url_list:
    print(x)
print(len(url_list))