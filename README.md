# Text Crawl

## 简介

**尝试从提供的URL抓取正文文本到本地。可提供普通的网页URL也支持一些小说网站的小说目录页，自动提取其正文保存合并为纯文本。**

核心过滤算法基于《基于行块分布函数的通用网页正文抽取算法》实现。
* 目录页模式，适用于小说抓取
* 单页模式，适用于提取普通页面正文
* 支持以当前页为基础向前或向后翻页
* 支持在页面有多段正文的提取
* 支持自定义核心参数，适应更多环境
* 支持抓取包含代码的正文，保持格式
* 支持多线程抓取
* 支持以邮件发送结果

目前不支持需要登录的页面


## 使用方法

> 仅支持Python3版本

### 简单使用示例

* 抓取某本小说，-c 目录模式 贴上小说目录页地址，可获得每节文本与合并的文本
```sh
python3 Text_Crawl.py -c http://book.qidian.com/info/1003516610#Catalog
```

* -m 1 降低线程倍数，适应速度较慢的网站
```sh
python3 Text_Crawl.py -c http://www.52dsm.com/chapter/6712.html -m 1
```
* 抓取某个页面的正文，-s 单页模式 贴上地址即可
```sh
python3 Text_Crawl.py -s http://news.mydrivers.com/1/505/505220.htm
```

* 获取某吧的同人正文。`-s`单页模式，`-pn`向后翻页，`-loop 3`页面循环查找，收集不小于平均段落长度1/3的文本
```sh
python3 Text_Crawl.py -s https://tieba.baidu.com/p/1061691931 -pn -loop 3
```


### 自定义使用示例


* 抓取某个同人文帖子中的正文并尝试自动抓取下一页。loop表示单页循环抓取（默认只过滤一次），pn表示翻页方向， pv表示最短的段落不小于最长段落的1/3 ，小于的会丢弃并在日志中显示，blank-remove 清除空格，这是因为贴吧的html很混乱。


```sh
python3 Text_Crawl.py -s http://tieba.baidu.com/p/4794348007 -loop -pn down -pv 3 --blank-remove
```


* 抓取一个包含代码的页面，目的是抓取正文并保留缩进。这个页面可发现正文较为分散，因此可能需要尝试不同的参数以获得最佳效果。-b是过滤算法的块参数，越大越包容，越小则丢弃越多，--dr绘图显示页面文本的分布函数 以便调整参数，-loop 5 单页循环抓取并设定最长段落与最短相差不超过5倍，dest 直接在终端输出结果。
```sh
python3 Text_Crawl.py -s http://beautifulsoup.readthedocs.io/zh_CN/latest/ -b 10 --dr -loop 5 -dest terminal
```

* 更多使用帮助
```
python3 Text_Crawl.py -h
```
