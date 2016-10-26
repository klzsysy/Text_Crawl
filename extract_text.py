# -*- coding: utf-8 -*-
import re
from public_features import get_url_to_bs, loggings, draw_processing
import itertools
import time


class extract(object):
    """
    通过《基于行块分布函数的通用网页正文抽取算法》实现
    有变动:
        1:直接取了分布函数最高点，然后向前后推进确定起始与结束点
        3:针对小说类页面过滤无效内容
            self.body = re.sub(reOTH, '', self.body)
            def processText(self):
        4:新增了使用递归处理可能出现多段正文的情况
    """
    def __init__(self, html="", block_size=4, image=False, leave_blank=True, drawing=True, repeat=False):
        """
        :param html:        html文档
        :param block_size:  文本块大小， 越小越严格，越大越宽松
        :param image:       保留图片url
        :param leave_blank: 保留文字中的空格
        :param drawing:     绘制文本分布函数图
        :param repeat:      重复过滤模式
        """
        self.reBODY = re.compile(r'<body.*?>([\s\S]*?)<\/body>', re.I)
        self.reCOMM = r'<!--.*?-->'
        self.reTRIM = r'<{0}.*?>([\s\S]*?)<\/{0}>'
        if leave_blank:
            self.reTAG = r'<[\s\S]*?>|[\t\r\f\v]'  # 保留空格
        else:
            self.reTAG = r'<[\s\S]*?>|[ \t\r\f\v]'  # 删除所有空格
        self.respa = r'(&nbsp;)+'
        self.relt = r'&lt;'
        self.regt = r'&gt;'
        self.reIMG = re.compile(r'<img[\s\S]*?src=[\'|"]([\s\S]*?)[\'|"][\s\S]*?>')

        self.html = html
        self.blocks_size = block_size
        self.save_image = image
        self.raw_page = ""
        self.c_texts = []
        self.minimum_effective_value = 100          # 段落最低文本
        self.store_text = []
        self.section = 1
        self.leave_blank = leave_blank
        self.drawing = drawing
        self.repeat = repeat
        # loggings.debug('blocks_size={0};save_image={1};leave_blank={2};drawing={3}repeat={4}'.format(self.blocks_size,
        #                 self.save_image, self.leave_blank, self.drawing, self.repeat))
        if self.drawing:
            self.Draw = draw_processing()

    def tags_process(self,):
        self.body = re.sub(self.reCOMM, "", self.body)
        self.body = re.sub(self.reTRIM.format("script"), "", re.sub(self.reTRIM.format("style"), "", self.body))
        self.body = re.sub(self.reTAG, "", self.body)
        self.body = re.sub(self.respa, '', self.body)
        # r'(&gt;)+' *次重复会导致0次匹配也成功的问题, 适用于有代码页面
        self.body = re.sub(self.relt, '<', self.body)
        self.body = re.sub(self.regt, '>', self.body)
        # 替换空白行为空
        while self.leave_blank:
            self.body, n = re.subn(r'\n +\n', '\n\n', self.body)
            # loggings.debug('del ... %s' % str(n))
            if n == 0:
                break

    def blocks_process(self, recursion=False):
        '''
        打开show_block_function可查看曲线图, 在断点bug的情况下可能无法显示图形，原因不明。
        :param recursion:   是否是尝试抓取第二段
        :return:            返回抽取的文本
        '''
        self.c_blocks = []
        self.c_texts_length = [len(x) for x in self.c_texts]
        '''生成块列表'''
        for x in range(len(self.c_texts) - self.blocks_size + 1):
            self.c_blocks.append(sum([len(y) for y in self.c_texts[x:x + self.blocks_size]]))

        # 首次过滤最长的文本段没有达到预定义的长度 则视为太短抛弃
        if max(self.c_texts_length) <= self.minimum_effective_value and not recursion:
            loggings.debug('文本长度小于预设值{}，被抛弃:\n{}\n{}\n{}'.format(self.minimum_effective_value, '-'*40,
                            self.c_texts[self.c_texts_length.index(max(self.c_texts_length))], '-' * 40))
            return None

        '''函数分布图的最高点'''
        max_block = max(self.c_blocks)
        self.start = self.end = self.c_blocks.index(max_block)
        """
        这里start与end点是大于 行块的最小值。
        point > N，通常这个最小值是0（空行就是0），增大N将会过滤掉长度小于N的行
        """
        self.N = min(self.c_blocks)
        while self.start >= 0 and self.c_blocks[self.start] > self.N:
            self.start -= 1

        while self.end < len(self.c_blocks) - 1 and self.c_blocks[self.end] > self.N:
            self.end += 1
        self._text = '\n'.join(self.c_texts[self.start + self.blocks_size: self.end])

        if self.drawing:self.Draw.put(self.c_blocks)                # 画图

        '''尝试再次获取有效文本，针对有多段有效文本的情况'''
        if not recursion:                                           # 第一次分析 获得本次字符串长度
            self.section = len(self._text)
            self.x = 1
        else:                                                       # 非第一次的递归操作
            loggings.debug('第%s次再分析完成' % self.x)
            if len(self._text) < int(self.section / self.repeat):             # 本次字符串长度小于第一次的一半则忽略
                loggings.debug('本次分析达不到预定义的要求(大于最长段落的1/{})，抛弃如下内容:'
                               '\n{}\n{}\n{}'.format(self.repeat, '-' * 100, self._text, '-' * 100))
                return None
        self.store_text.append([self.start, self._text])            # 收集有效的段落
        # 删除已提取的段落
        self.c_texts = self.c_texts[:self.start + self.blocks_size] + self.c_texts[self.end:]
        # 开始递归操作,查找符合调节的第二段文本
        if self.repeat:
            self.x += 1
            self.blocks_process(recursion=True)
        return self.store_text

    def del_invalid_text(self):
        """删除特定组合的内容 解决一些靠分布算法不好搞的内容"""
        lists = ("（快捷键←）",
                 "上一章", "返回目录", "加入书签", "推荐本书", "返回书页", "下一章", "（快捷键→）",
                 "投推", "荐票", "回目录", "标记", "书签", "登陆", "注册",'新用户', 'FAQ', '道具', '商城', '每日任务',
                 '咨询', '投诉', '举报'
                 )
        self.f = self.finally_text.split('\n')
        index = []

        def iter_text(self):
            """定位到单行内成功匹配三个关键字的行index值"""
            for x in self.f:
                for i in itertools.combinations(lists, r=3):
                    ass = 0
                    for ii in i:
                        if ii in x:
                            ass += 1
                    if ass >= 3:
                        index.append(self.finally_text.index(x))
                        break

        '''在匹配到上诉三个关键词的行截断首尾'''
        iter_text(self)
        if len(index) == 1 and index[0] > len(self.finally_text) / 2:
            self.finally_text = self.finally_text[:index[0]].strip()
        if len(index) >= 2:
            start = max(x for x in index if x < len(self.finally_text) / 2)
            end   = min(y for y in index if y > len(self.finally_text) / 2)
            self.finally_text = self.finally_text[start:end]

    def crawl_context(self):
        self.raw_page = self.html
        try:
            self.body = re.findall(self.reBODY, self.raw_page)[0]
        except BaseException:
            # 某些body异常的网页
            self.body = self.raw_page
        if self.save_image: self.body = self.reIMG.sub(r'{{\1}}', self.body)
        self.tags_process()
        self.c_texts = self.body.split("\n")
        self.text = self.blocks_process()

        if self.drawing:
            time.sleep(1)
            self.Draw.put(None)                         # 确保绘图子进程结束后主线程可以退出
            loggings.debug('多线程绘图进程已结束')

        if self.text is None:
            return None
        # 排序并组合二维列表为字符串
        self.finally_text = '\n\n# ---------------\n\n'.join(y[1] for y in sorted(self.text, key=lambda x: x[0]))
        self.del_invalid_text()

        return self.finally_text


def extract_text(page_link, page_tiele, args=None):
    '''
    请求URL并提取主要文本
    :return: UTF-8编码的字符串和页面标题
    '''
    loggings.debug('Start Read %s' % page_link + page_tiele)
    page_soup, _, _, _, _ = get_url_to_bs(page_link, re_count=args.retry)
    get_page_tiele = page_soup.title.get_text()
    if page_tiele == '':
        page_tiele = get_page_tiele

    loggings.debug('Read Complete [%s]' % page_tiele)

    ext = extract(html=str(page_soup), block_size=args.block_size,
                  leave_blank=args.leave_blank, drawing=args.drawing, repeat=args.repeat)

    loggings.info('Start trying to filter the page text [%s]' % page_tiele)
    text = ext.crawl_context()

    if text is None:
        raise IndexError('No valid text to extract, possibly invalid pages, '
                         'or to confirm that a requested site needs to log in. [%s]' % page_tiele)

    loggings.debug('Page text filtering is complete [%s]' % page_tiele)
    text = page_tiele + '\n\n' + text
    """编码转换 极为重要，编码成utf-8后解码utf-8 并忽略错误的内容"""
    text = text.encode('utf-8').decode('utf-8', 'ignore')
    return text, page_tiele
