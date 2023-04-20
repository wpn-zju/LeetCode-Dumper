# LeetCode-Dumper

[English](https://github.com/wpn-zju/LeetCode-Dumper/blob/main/README.md)

提取你的LeetCode已提交AC代码

# 安装依赖
1. 通过 `pip` 安装 [chevron](https://github.com/noahmorrison/chevron) - mustache 模板工具的 python 实现。`pip3 install chevron`.

# 特性
1. 同时支持LeetCode[国际版](https://leetcode.com)和[中国版](https://leetcode.cn)
1. 利用并发请求实现数分钟内提取上千个问题
1. 支持自定义需要提取的题号

# 使用方法
1. 在使用本工具之前你必须获取账号对应的 cookie 值，已通过网站的签名验证。
1. 打开国际版或者中国版 LeetCode 任意页面，打开 `DevTools` ，在 `Network` 中选择 `Fetch/XHR` ，找到任意的 GraphQL 请求，打开后在 request header 部分找到并复制完整的 cookie 值。
1. `python grab.py -d cn -c <cookie>`
1. 等待提取完成

![devtools](devtools-screenshot.png)

# Todo
1. 添加选项 - 一次性提取所有 AC 代码
1. 添加选项 - 自定义输出路径
1. 添加更多 language extension tags
1. 添加提交的 metadata，其中包含运行时间分布、内存使用分布等等，以注释的形式
1. 添加范围提取选项。例如 `python grab.py -c <cookie> -r <min>-<max>`
1. 添加强制覆盖以提取代码的选项
1. 添加题目描述

# Troubleshooting
## 语言代码未找到
```
Question #1549 - Code extension not found, please manually add the extension name into the script, lang code [mysql].
```

如果的使用的编程语言不在 file extension mapping 中并出现以上提示，请先在脚本中手动添加对应 mapping 关系。

## 部分请求失败
```
Question #1207 - 'NoneType' object is not subscriptable
```

由于多线程下载触发了 LeetCode 的请求阈值，因此部分请求返回无效结果导致失败。遇到此问题可尝试反复运行此脚本或通过设置 `-t=<threads>` 降低并发数量。

# 仓库示例
https://github.com/wpn-zju/LeetCode-Dump

# 感谢
https://github.com/enh6/leetcode/blob/master/grab_solutions.py
