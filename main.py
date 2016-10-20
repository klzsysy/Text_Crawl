# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import re
import os
import sys
import urllib.request
import public_features as PF
from extract_text import extract_text
import threading

'''最大重试次数'''
retry_count = 3
'''目录页URL'''
html_url = 'http://www.piaotian.net/html/5/5924/'


def extract_url(ori_url):
    '''
    提取目录页的有效URL，抓取网站title
    :param ori_url: 目录页URL
    :return:        提取的章节URL 列表
    '''

    soup_text, protocol, domain, rest, code = PF.get_url_to_bs(ori_url, re_count=2)
    # headers = {'User-Agent':
    #     'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    #     ' AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'
    # }
    # request = urllib.request.Request(ori_url, headers=headers)
    # result = urllib.request.urlopen(request, timeout=15)
    # content = result.read()
    # info = result.info()
    # loggings.info('read original URL complete！')
    # # 获取协议，域名
    # protocol, rest = urllib.request.splittype(ori_url)
    # domain = urllib.request.splithost(rest)[0]
    # result.close()

    if 'qidian.com' in domain:
        import qidian_config
        PF.loggings.info('go to qidian configure')
        qidian_config.main(ori_url)
        sys.exit(0)

    # soup = BeautifulSoup(content, 'html5lib')
    # soup_text = soup.select('li > a')
    GET_PAGE_LINKS = PF.get_page_links(soup_text, rest, protocol)
    all_page_links = GET_PAGE_LINKS.get_href()
    # links = []
    # count = 0
    # for tag in soup_text:
    #     try:
    #         link = tag.attrs.get('href')
    #     except BaseException:
    #         pass
    #     else:
    #         if re.match('^javascript|/?class', link):
    #             continue
    #         if re.match('^\d+\.\S{1,5}$|/\S+\.\S{1,5}$', link):     # '单节数值' 与 '多节组合'
    #             merge_link = PF.url_merge(rest, link)
    #             links.append([count, protocol + '://' + merge_link])
    #             count += 1
    #             continue
    #         if re.match('^(https?://)?((\w+\.)?\S+?\.\w+){1}/[^\s]+', link):    # 完整URL
    #             links.append([count, link])
    #             count += 1

                # print('add:' + link)
    PF.loggings.info('Analysis of original URL success')
    PF.loggings.debug('start get website title...')

    # donain_title_text = ''

    webstie_bs, _, _, _, _ = PF.get_url_to_bs(protocol + '://' + domain, re_count=1)
    donain_title_text = webstie_bs.title.get_text()
    # def website_title():
    #     try:
    #         domain_request = urllib.request.Request(protocol + "://" + domain, headers=headers)
    #         domain_result = urllib.request.urlopen(domain_request, timeout=15)
    #         domain_content = domain_result.read()
    #         domain_result.close()
    #         donain_soup = BeautifulSoup(domain_content, 'html5lib')
    #         text = donain_soup.title.get_text()
    #     except BaseException as err:
    #         loggings.error(str(err))
    #         loggings.debug('retry get website title ')
    #         return False, ''
    #     else:
    #         loggings.info('get website title complete！')
    #         return True, text
    # while website_title_retry > 0:
    #     website_title_retry -= 1
    #     status, donain_title_text = website_title()
    #     if status:
    #         break

    return all_page_links, len(all_page_links), donain_title_text, domain


def process(fx, link_list, retry, domain_title):
    '''
    章节页面处理
    :param fx:          提取文本
    :param link_list:   页面URL总列表
    :param retry:       失败重试次数
    '''
    PF.try_mkdir(PF.Down_path)

    while link_list:
        pop = link_list.pop(0)      # 提取一条链接并从原始列表删除
        count = pop[0]              # 序号
        link = pop[1]               # 超链接
        try:
            page_text, title = fx(link, domain_title)

        except BaseException as err:

            PF.loggings.warning('%s read data fail' % link + str(err))
            PF.loggings.debug('%s %s add timeout_url list' % (count, link))
            timeout_url.append([count, link])
        else:
            '''写入文件'''
            if page_text:
                D = PF.Decodes()
                '''              当前序号 标题     文本内容   总页面数'''
                wr = D.write_text(count, title, page_text, page_count)
                if not wr:
                    Unable_write.append([count, link])
                    PF.loggings.error(count+title+' Unable to save!!!')

    '''处理异常的链接'''
    if len(timeout_url) > 0 and retry > 0:
        PF.loggings.debug('Retry the %s time' % retry)
        retry -= 1
        process(fx=extract_text, link_list=timeout_url, retry=retry, domain_title=domain_title)
    if len(timeout_url) > 0 and retry == 0:
        PF.loggings.error('重试 %s次后，以下列表仍无法完成:' % retry)
        for x in timeout_url:
            print(x[0] + x[1])
            PF.loggings.info('script quit, But an error has occurred :(')
            os._exit(-1)


def multithreading():
    """
    页面处理多线程化
    """
    class mu_threading(threading.Thread):
        def __init__(self):
            threading.Thread.__init__(self)
            self.daemon = True
            self.retry_count = retry_count

        def run(self):
            process(extract_text, links, self.retry_count, domain_title=domain_title)

    mu_list = []
    for num in range(os.cpu_count()):
        M = mu_threading()
        mu_list.append(M)
        M.start()           # 开始线程
    for mu in mu_list:
        mu.join()           # 等待所有线程完成
    PF.loggings.info('Multi-threaded to complete! , There is no error ')


if __name__ == '__main__':
    timeout_url = []
    Unable_write   = []
    '''从目录页面提取所有章节URL'''
    links, page_count, domain_title, domain = extract_url(html_url)
    '''多线程处理处理章节URL'''
    # multithreading()

    # process(fx=extract_text, link_list=[[1000, 'http://read.qidian.com/BookReader/9sW8fN_RiY7xq9ZHzk0vMw2,aJRPRNdLgHDwrjbX3WA1AA2.aspx']],
    #         retry=retry_count, domain_title=domain_title)
    # '''单线程处理章节URL列表'''
    process(fx=extract_text, link_list=links, retry=retry_count, domain_title=domain_title)
    '''合并文本'''
    PF.text_merge(os.path.abspath('.'), count=page_count)

    if len(Unable_write) == 0:
        PF.loggings.info('script complete, Everything OK!')
        sys.exit(0)
    PF.loggings.info('script complete, EBut there are some errors :(')
    PF.loggings.error('Unable to write to file list:')
    print(Unable_write)
    sys.exit(1)

    # process(fx=extract_text, link_list=[[1000,'http://www.piaotian.net/html/5/5924/4289022.html']], retry=retry_count)
