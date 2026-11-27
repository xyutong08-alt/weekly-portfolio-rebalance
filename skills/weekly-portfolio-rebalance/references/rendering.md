# Word 预览与增量复核

数据提取期间按批保存JSON、Word并做往返核对，不必每批渲染图片。首次生成时先做小样，确认中文标题、表头和基金名可见；将已答复的同批异常处理好后集中渲染。起始周五仍须先交付本期Word，再由用户决定补录，不能为等确认扣留Word。

## 中文字体预检

沿用历史Word字体，不为预览修改交付文档的字体。通过宿主文档工具查到当前捆绑的Python、LibreOffice和字体工具；不要猜其他机器的运行时路径或改用用户桌面LibreOffice。

首次渲染先检查SimSun或可用中文字体。捆绑环境提供`fc-list`时可运行：

```bash
python3 SKILL/scripts/render_review.py fonts --workdir /本期目录/preview-config --fc-list /当前捆绑路径/fc-list
```

输出`fontconfig_file`时，仅在本次预览进程设置`FONTCONFIG_FILE`为该文件，再用宿主`render_docx.py`渲染；后续`pages`命令使用相同的`FONTCONFIG_FILE`。脚本优先保留已安装SimSun，否则从实际检测到的STSong、Noto Serif CJK SC、Songti SC、Arial Unicode MS中选取别名；不下载字体、不改系统配置、不改Word文件。macOS已验证STSong可避免中文缺字及Songti SC在此环境中的行高膨胀。

未提供Fontconfig工具的宿主可用原生文档预览检查中文；不要因脚本不可用反复尝试相同整篇渲染。预检失败时先修复字体或明确报告预览受限；字符已在Word XML中但图片不可见，不能误判为源数据缺失。字体替换、渲染器或DPI改变后，旧排版检查结论全部失效。

## 页面复核记录

最终版本必须覆盖全部页面的视觉检查。补录或修改后重新渲染，不能只看尾页：前页的换行可能引起后续分页改变。图片放入新的或已清空的本期预览目录，防止把上一版多余页当作本期页面。

```bash
python3 SKILL/scripts/render_review.py pages --images /本期目录/本次预览 --manifest /本期目录/review.json --context "当前渲染器版本及DPI及字体配置标识"
```

只输出待检查页号`to_review`、已检查且图像哈希完全一致的页号`reused`和页数。逐页打开`to_review`，确认中文、长基金名换行、表格、页边界、表头和空白页；完成后才记录实际检查的页：

```bash
python3 SKILL/scripts/render_review.py pages --images /本期目录/本次预览 --manifest /本期目录/review.json --context "同一预览环境标识" --approve-pages 1 2 3
```

哈希相同但从未检查过的页不能复用。`context`应包含渲染器版本、DPI、字体设置；设置了`FONTCONFIG_FILE`时脚本另计其内容哈希。没有旧清单、环境变化或字体预览曾失败时，从全部当前页面开始检查。图片比对只减少重复图片输入，不代替基金数量、前后权重及Word往返核对，也不意味着脚本已自动审阅页面。
