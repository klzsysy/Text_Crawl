# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import re
import urllib.request
from public_features import loggings
from public_features import detcet_charset, decodes


def extract_text(page_link):
    page_get = urllib.request.urlopen(page_link, timeout=10)
    page_read = page_get.read()
    page_get.close()
    loggings.debug('%s Read complete!' % page_link)
    # page_chatset = detcet_charset(page_read)
    # page_get.encoding = page_chatset

    # page_read, page_charset = decodes(page_read)
    '''
    html5lib:       最好的容错性,以浏览器的方式解析文档,生成HTML5格式的文档,速度慢
    html.parser:    Python的内置标准库,执行速度适中,文档容错能力强
    lxml:           速度快,文档容错能力强
    '''
    page_soup = BeautifulSoup(page_read, 'html5lib')
    '''获取标题'''
    title = page_soup.title.get_text()
    title = title.split(',')[1]
    '''获取文本'''
    page_text   = page_soup.select('body')[0].get_text()
    '''定位正文前的标题位置'''
    start_index = page_text.index(title)
    '''标记一个结尾位置'''
    end_index   = page_text.index('|')

    ''' 选定标题到结尾的文本 '''
    page_text_2 = page_text[start_index:end_index]
    page_text_2 = page_text_2[:page_text_2.rindex('\n')]

    '''选定正文'''
    index_1 = page_text_2.index('\n\n')
    page_text_3 = page_text_2[index_1+1:].strip()

    text = ''
    for line in page_text_3.splitlines():
        if re.search('\S+', line):              # 判定是否空行
            line = line.strip()
            text += line+'\n'
        else:
            pass                                # 丢弃空行
    text = title + '\n\n' + text
    return text, title

