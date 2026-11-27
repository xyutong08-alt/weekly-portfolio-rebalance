# 每周调仓汇总 · Codex Skill

从投顾星球已登录网页或用户提供的截图提取调仓明细，检查重复、基金数量与权重，生成指定日期区间的 Word 汇总，通常使用近七日。

## 安装

把仓库链接交给 Codex，并说：

> 请从 https://github.com/xyutong08-alt/weekly-portfolio-rebalance/tree/main/skills/weekly-portfolio-rebalance 安装 weekly-portfolio-rebalance 技能。

完整技能在 `skills/weekly-portfolio-rebalance/`，入口为 [SKILL.md](skills/weekly-portfolio-rebalance/SKILL.md)。请安装整个目录，包含 scripts、references 和 agents，不能只复制 SKILL.md。

## 使用

> 使用 $weekly-portfolio-rebalance 整理【开始日期】至【结束日期】的调仓，文件保存在【你的调仓文件夹路径】。

1. 在支持浏览器操作的 Codex 环境中打开 https://strategy1.post.advisorplanet.cn/adminweb/strategy-library 。
2. 使用自己的获授权账号登录；密码、短信或图形验证码由使用者在网页中完成。
3. 指定任意起止日期；若恰为上周五至本周五，在投顾星球选择“近七日/近7日”。其他区间使用自定义日期，并按用户要求核对边界和分页。
4. 常规周先整理近七日并产出 Word。起始上周五通常已在上期汇总，不自动补入；Word 产出后，再把该周五的策略清单列在聊天里，与上期记录核对，由使用者点名决定哪些补入。
5. 找不到上期记录（例如他人使用、新开窗口或文件缺失）时，直接列出该周五清单，标为“未核对上期记录”，由使用者选择，不自动判定已录或漏录，也不阻塞本期 Word 交付。
6. 只对点名批准的策略拉取完整明细并追加。数据保存在本地 JSON，Word 由数据全量生成；后续可发送截图补录。

此技能由 Codex 执行网页操作，不是独立运行的爬虫或定时任务。需要浏览器/电脑操作工具才能自动读取网页；没有这些工具时可通过截图补录。本地记录脚本仅需 Python 3 标准库，Word 排版预览按使用环境配置。

## 已包含的检查

- 机构排除、多期系列只留一期、本期去重及上期对照；起始周五按使用者确认补录。
- 同权重但名称不同的组合先请使用者决定。
- 基金数量、资产组合计、全部持仓权重与页面操作标签。
- 保留“分类缺失”基金，基准未给时标记待补充。
- 追加前备份，生成后检查 Word 与 JSON 的记录一致。

具体收录规则见 [references/rules.md](skills/weekly-portfolio-rebalance/references/rules.md)，可按自己的业务口径调整。默认目录由使用者指定，不依赖作者电脑路径。

## 减少token消耗

- 规则按需加载，网页只提取相关字段，不反复输出整页业绩和历史记录。
- 记录工具默认只报告编号、数量和异常；完整基金数据仍保存在本地，排查问题时才用 `--verbose`。
- 简短总结使用 `record_week.py summary`，避免先输出整周持仓。

## 文件

- SKILL.md：技能入口与流程。
- agents/openai.yaml：技能显示名称与示例调用。
- references/：网页读取、收录规则、数据格式与脚本用法。
- scripts/record_week.py：预检查、去重、追加及备份。
- scripts/weekly_rebal.py：Word 生成、导入及统计辅助。

仓库不包含登录凭证、验证码、用户截图、历史调仓文档或实际周数据。技能只执行数据读取与本地记录，不执行投资交易。

## 许可证

[MIT](LICENSE) — 允许使用、修改和分发，保留版权与许可声明。
