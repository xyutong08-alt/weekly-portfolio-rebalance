# 每周调仓汇总 · Codex Skill

从投顾星球已登录网页或用户提供的截图提取调仓明细，检查重复、基金数量与权重，生成每周 Word 汇总。

## 安装

把仓库链接交给 Codex，并说：

> 请从 https://github.com/xyutong08-alt/weekly-portfolio-rebalance 安装 weekly-portfolio-rebalance 技能。

本仓库根目录即完整技能目录，入口为 [SKILL.md](SKILL.md)。请安装整个目录，包含 scripts、references 和 agents，不能只复制 SKILL.md。

## 使用

> 使用 $weekly-portfolio-rebalance 整理11月23日至27日的调仓，文件保存在【你的调仓文件夹路径】。

1. 在支持浏览器操作的 Codex 环境中打开 https://strategy1.post.advisorplanet.cn/adminweb/strategy-library 。
2. 使用自己的获授权账号登录；密码、短信或图形验证码由你在网页中完成。
3. 登录后由 Codex进入“调仓动态”，按日期逐页覆盖记录，进入每个详情核对完整名称、基准及全部基金。
4. 数据保存在本地 JSON，Word 由数据全量生成。后续也可发送截图继续补录。

此技能由 Codex 执行网页操作，不是独立运行的爬虫或定时任务。需要浏览器/电脑操作工具才能自动读取网页；没有这些工具时可通过截图补录。本地记录脚本仅需 Python 3 标准库，Word 排版预览按使用环境配置。

## 已包含的检查

- 机构排除、多期系列只留一期、当周和上周去重。
- 同权重但名称不同的组合先请使用者决定。
- 基金数量、资产组合计、全部持仓权重与页面操作标签。
- 保留“分类缺失”基金，基准未给时标记待补充。
- 追加前备份，生成后检查 Word 与 JSON 的记录一致。

具体收录规则见 [references/rules.md](references/rules.md)，可按自己的业务口径调整。默认目录由使用者指定，不依赖作者电脑路径。

## 文件

- SKILL.md：技能入口与流程。
- agents/openai.yaml：技能显示名称与示例调用。
- references/：网页读取、收录规则、数据格式与脚本用法。
- scripts/record_week.py：预检查、去重、追加及备份。
- scripts/weekly_rebal.py：Word 生成、导入及统计辅助。

仓库不包含登录凭证、验证码、用户截图、历史调仓文档或实际周数据。技能只执行数据读取与本地记录，不执行投资交易。
