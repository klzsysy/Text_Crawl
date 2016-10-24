# -*- coding: utf-8 -*-
"""
来源 http://www.jianshu.com/p/bc6df6a38c66
"""
import urllib.request
import chardet
import time
import random
from bs4 import BeautifulSoup as bs
import os
from public_features import down_path, try_mkdir, loggings
import requests
import re

ISOTIMEFORMAT='%Y-%m-%d %X'

save_path = os.path.join('.', down_path)
#通用装饰器1
def writeBook(func):
    def swr(*args,**kw):
        f = open(os.path.join(save_path, args[-1] + '.txt'), 'a+', encoding='utf-8')
        f.write('\n\n')
        result = func(*args, **kw)
        f.write('>')
        return result
    return swr
#创建文件并定义名称
def createBook(bookName):
    f=open(os.path.join(save_path,  bookName + '.txt'), 'a', encoding='utf-8')

#写卷目录
def createTitle(title,bookName):
    f=open(os.path.join(save_path, bookName+'.txt'), 'a', encoding='utf-8')
    f.write('\n\n### ' + title)

#写每卷中对应的章节目录
def writeZhangjie(menuContentBs, bookName,i):
    menuZhangJie = menuContentBs.find_all("div", "box_cont")[1:]
    menuZhangJieS = bs(str(menuZhangJie[i]), 'html.parser')
    menuZhangJieSpan = menuZhangJieS.find_all('span')
    menuZhangJieHref = menuZhangJieS.find_all('a')
    menuZhangJieHrefList = getHref(menuZhangJieHref)
    writeZhangjieDetail(menuZhangJieSpan, bookName,menuZhangJieHrefList)

def writeZhangjie2(menuContentBs, bookName,i):
    menuZhangJie = menuContentBs.find_all("div", "box_cont")[0:]
    menuZhangJieS = bs(str(menuZhangJie[i]), 'html.parser')
    menuZhangJieSpan = menuZhangJieS.find_all('span')
    menuZhangJieHref = menuZhangJieS.find_all('a')
    menuZhangJieHrefList = getHref(menuZhangJieHref)
    writeZhangjieDetail(menuZhangJieSpan, bookName,menuZhangJieHrefList)

# 写章节细节和每章内容的方法(还有点问题)

def writeZhangjieDetail(menuZhangJieSpan, bookName,menuZhangJieHrefList):
    x = 0
    for spanValue in menuZhangJieSpan:
        # timeout = random.choice(range(80, 180)) / 100
        # loggings.debug('延时：' + str(timeout))

        spanValue = bs(str(spanValue), 'html.parser').get_text()

        loggings.debug('{:<3}{:<20}{:<12}{:<}'.format(str(x) , spanValue , '--执行到此章节--', str(time.strftime(ISOTIMEFORMAT, time.localtime())))) #打印已经写到哪个章节
        f = open(os.path.join(save_path, bookName + '.txt'), 'a', encoding='utf-8')
        f.write('\n\n---')
        f.write('\n\n#### ' + spanValue + '\n\n')
        try:
            # chapterCode = urllib.request.urlopen(menuZhangJieHrefList[j]).read()
            re_chapter = requests.get(menuZhangJieHrefList[x])
            chapterCode = re_chapter.content

            re_chapter.close()
            chapterSoup = bs(chapterCode, 'html.parser')  # 使用BS读取解析网页代码
            chapterResult = chapterSoup.find(id='chaptercontent')  # 找到id='chaptercontent'的节点
            chapterResultChilds = chapterResult.children

            story_src = bs(str(list(chapterResultChilds)[3]), "html.parser")
            fileurl = story_src.contents[0].attrs['src']

            file_re = requests.get(fileurl)
            file_content = file_re.content
            file_bs = bs(file_content, 'html5lib')
            text_file = str(file_bs)
            file_re.close()
            text_file = re.sub('<[\s\S]*?>|[ \t\r\f\v]', '', text_file)
            text_file = re.sub('\S+\(|\);|\\n+', '', text_file)
            text_file = re.sub('起点中文.*', '', text_file)

            text_file = text_file.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
            f.write(text_file)
        except BaseException as err:
            f.write('章节丢失')
            loggings.error('章节丢失 %s' % str(err))
        x += 1


#获取各个章节的URL
def getHref(menuZhangJieHref):
    menuZhangJieHrefList = []
    for index in menuZhangJieHref:
        menuZhangJieHrefList.append(index.get('href'))
    return menuZhangJieHrefList

def write(menuContentBs,menu,n):
    i = 0
    for index in menu:
        MuLu = bs(str(index), 'html.parser')
        MLb = MuLu.find('b')
        MuLua = bs(str(MLb), 'html.parser')
        MLa = MuLua.find('a')
        forTitle = bs(str(MLa), 'html.parser')
        muluTitle = MuLua.get_text()
        bookName = forTitle.get_text()
        createBook(bookName)
        createTitle(muluTitle, bookName)
        # MD文件和卷标题写好，就要写入正式的章节目录和文本内容
        if n==0:
            writeZhangjie2(menuContentBs, bookName, i)
        else:
            writeZhangjie(menuContentBs, bookName, i)
        print(str(i + 1), 'xx', '--执行到此目录', str(time.strftime(ISOTIMEFORMAT, time.localtime())))  # 打印已经写入的目录
        i += 1
        # time.sleep(1)

def main(url):
    try_mkdir(save_path)

    webStory = urllib.request.urlopen(url).read().decode('utf8',errors='replace')          #获取整个网页

    loggings.debug('开始：' + time.strftime( ISOTIMEFORMAT, time.localtime() ))
    soup = bs(webStory,'html.parser')                       #解析整个网页
    menuContent = soup.find_all(id="content")              #获取解析好的网页上id位content的元素
    #menuContentStr = ','.join(str(v) for v in menuContent)  #将 menuContent转换为str 如果有多个
    menuContentBs = bs(str(menuContent),'html.parser')       #解析转换好的menuContentStr为bs对象

    menu = menuContentBs.find_all("div", "box_title")[0:1]
    if('正文卷' in bs(str(menu),'html.parser').get_text()):
        menu = menuContentBs.find_all("div", "box_title")[0:]  # 从解析好的bs对象中获取是div且class为box_title的元素
        write(menuContentBs,menu, 0)
    else:
        menu = menuContentBs.find_all("div", "box_title")[1:]  # 从解析好的bs对象中获取是div且class为box_title的元素
        write(menuContentBs,menu, 1)
    #soup2 = bs(str(menu),'html.parser')                       #转换为bs对象

    loggings.info('结束：' + str(time.strftime( ISOTIMEFORMAT, time.localtime() )))
