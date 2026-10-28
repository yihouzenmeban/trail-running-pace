# Pace

跑步、越野跑与配速相关资料。

## 已归档文章

- `耐力科学_体感一致配速表全面指南.md`：由用户提供的 18 页 PDF 整理，保留原文正文、图示、作者介绍和版权声明。
- `assets/pace-chart/`：文章引用的 17 张图片，包括配速表示例、掉速曲线、跑力包线和比赛完成时间对照表。

原文标题：耐力科学|体感一致配速表全面指南。发布账号：耐力學社。原文注明文章来源于隆景体育，作者耐力学社。发布时间：2025 年 8 月 26 日 07:27（中国香港）。

原文链接：https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng

## PDF 整理方式

本次使用全局安装的 OpenDataLoader PDF 2.5.16，在本地导出 Markdown、JSON 和独立图片：

```bash
opendataloader-pdf \
  --format markdown,json \
  --image-output external \
  --output-dir /tmp/pace-opendataloader \
  '/Users/yihouzenmeban/Downloads/耐力科学_体感一致配速表全面指南.pdf'
```

解析后核对 PDF 页面，统一中文兼容字和标题层级，修复断词、跨页断句及丢失的连字符，将图片引用调整为仓库内的相对路径。原始 JSON 和临时预览保留在仓库外。

## 来源与版权

本仓库的文章是对用户提供资料的格式整理。原文关于知识方案、制表工具及生成配速表的不同版权说明，完整保留在文章的“五、版权声明”中；整理不改变这些声明。
