# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import re
import os
import sys
import requests
import chardet
import urllib.request
from public_features import loggings, Decodes, text_merge , Down_path
from extract_text import extract_text
import threading

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
    '''
    提取目录页的有效URL
    :param ori_url: 目录页URL
    :return:        提取的章节URL 列表
    '''
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
    return links, count


def process(fx, link_list, retry):
    '''
    章节页面处理
    :param fx:          提取文本
    :param link_list:   页面URL总列表
    :param retry:       失败重试次数
    '''
    if not os.path.isdir(Down_path):
        try:
            os.mkdir(Down_path)
            loggings.debug("create %s complete" % Down_path)
        except BaseException:
            raise OSError('can not create folder %s' % Down_path)

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
            '''写入文件'''
            D = Decodes()
            '''              当前序号 标题     文本内容   总页面数'''
            wr = D.write_text(count, title, page_text, page_count)
            if not wr:
                loggings.error(count+title+' Unable to save!!!')

    '''处理异常的链接'''
    if len(timeout_url) > 0 and retry > 0:
        loggings.debug('Retry the %s time' % retry)
        retry -= 1
        process(fx=extract_text, link_list=timeout_url, retry=retry)
    if len(timeout_url) > 0 and retry == 0:
        loggings.error('重试 %s次后，以下列表仍无法完成:' % retry)
        for x in timeout_url:
            print(x[0] + x[1])
            loggings.info('script quit, But an error has occurred :(')
            os._exit(-1)


def multithreading():
    '''
    页面处理多线程化
    '''
    class mu_threading(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
            self.daemon = True
            self.retry_count = retry_count

        def run(self):
            process(extract_text, links, self.retry_count)

    mu_list = []
    for num in range(os.cpu_count()):
        M = mu_threading()
        mu_list.append(M)
        M.start()           # 开始线程
    for mu in mu_list:
        mu.join()           # 等待所有线程完成
    loggings.info('Multi-threaded to complete! , There is no error ')


if __name__ == '__main__':
    timeout_url = []
    '''从目录页面提取所有章节URL'''
    links, page_count = extract_url(html_url)
    '''多线程处理处理章节URL'''
    multithreading()
    # '''单线程处理章节URL列表'''
    # process(fx=extract_text, link_list=links, retry=retry_count)
    '''合并文本'''
    text_merge(os.path.abspath('.'), count=page_count)

    loggings.info('script complete, Everything OK!')
    sys.exit(0)

    # process(fx=extract_text, link_list=[[1000,'http://www.piaotian.net/html/5/5924/4289022.html']], retry=retry_count)
