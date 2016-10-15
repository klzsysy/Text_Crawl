# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import re
import os
import sys
import requests
import chardet
import urllib.request
from public_features import loggings, Decodes
from extract_text import extract_text


retry_count = 3
html_url = 'http://www.piaotian.net/html/5/5924/'
# re_url = requests.get(url=html_url)
# re_url.encoding = 'gbk'
# re_url.close()
# soup = BeautifulSoup(re_url, 'html5lib')
# soup = BeautifulSoup(open('url.html'), 'html5lib')
# soup_text = soup.select('li > a')
# links = []
# print(repr(soup))


def extract_url(ori_url):
    result = urllib.request.urlopen(ori_url, timeout=15)
    content = result.read()
    info = result.info()
    loggings.info('read original URL complete！')
    # 获取协议，域名
    proto, rest = urllib.request.splittype(html_url)
    domain = urllib.request.splithost(rest)[0]

    # charset = page_features.detcet_charset(content)

    result.close()
    soup = BeautifulSoup(content, 'html5lib')
    soup_text = soup.select('li > a')
    links = []
    count = 0
    for tag in soup_text:
        try:
            link = tag.attrs.get('href')
        except BaseException:
            pass
        else:
            if re.match('^\d+', link):
                links.append([count, proto + '://' + rest.strip('/') + '/' + link])
                count += 1
                # print('add:' + link)
    loggings.info('Analysis of original URL success')
    return links


def process(fx, link_list, retry):
    if not os.path.isdir('down_text'):
        try:
            os.mkdir('down_text')
            loggings.debug("create 'down_text' complete")
        except BaseException:
            raise OSError('can not create folder down_text')

    while link_list:
        pop = link_list.pop(0)      # 提取一条链接并从原始列表删除
        count = pop[0]              # 序号
        link = pop[1]               # 超链接
        try:
            page_text, title = fx(link)
        except BaseException as err:
            loggings.warning('%s read data fail' % link + str(err))
            loggings.debug('%s %s add timeout_url list' % (count, link))
            timeout_url.append([count, link])
        else:
            D = Decodes()
            wr = D.write_text(count, title, page_text)
            if not wr:
                loggings.error(count+title+' Unable to save!!!')

    if len(timeout_url) > 0 and retry_count > 0:        # 处理异常的链接
        loggings.debug('Retry the %s time' % retry)
        retry -= 1
        process(fx=extract_text, link_list=timeout_url, retry=retry)
    if len(timeout_url) > 0 and retry == 0:
        loggings.error('重试 %s次后，以下列表仍无法完成:' % retry_count)
        for x in timeout_url:
            print(x[0] + x[1])
            loggings.info('script quit, But an error has occurred :(')
            sys.exit(1)
    loggings.info('script complete, Everything OK!')
    sys.exit(0)

if __name__ == '__main__':
    timeout_url = []
    '''从目录页面提取所有章节URL'''
    links = extract_url(html_url)
    '''处理章节URL列表'''
    process(fx=extract_text, link_list=links, retry=retry_count)

    '''debug'''
    # process(fx=extract_text, link_list=[[1000, 'http://www.piaotian.net/html/5/5924/4289022.html']], retry=retry_count)


