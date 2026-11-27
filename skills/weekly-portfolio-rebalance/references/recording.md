# 本地记录工具

脚本仅需Python标准库。以下的 `SKILL` 代表当前技能文件夹绝对路径；执行前用真实路径替换。`record_week.py`负责安全追加，`weekly_rebal.py`是沿用的Word生成器。

支持任意起止日期（均包含），不要求周五。示例命令中的开始日期和结束日期应替换为用户实际要求；仅给 `--end` 的兼容写法仍用于周五至周五任务。

```bash
python3 SKILL/scripts/record_week.py init --data /工作目录/指定区间/data.json --start YYYY-MM-DD --end YYYY-MM-DD
python3 SKILL/scripts/record_week.py init --data /工作目录/rebal_1120-1127/data.json --end 2026-11-27
python3 SKILL/scripts/record_week.py init --data /工作目录/rebal_1120-1127/data.json --from-docx /工作目录/本周调仓汇总_1120-1127.docx
python3 SKILL/scripts/record_week.py preview --data /工作目录/rebal_1120-1127/data.json --batch /工作目录/batch.json --previous /工作目录/本周调仓汇总_1113-1120.docx
python3 SKILL/scripts/record_week.py append --data /工作目录/rebal_1120-1127/data.json --batch /工作目录/batch.json --out /工作目录/本周调仓汇总_1120-1127.docx --previous /工作目录/本周调仓汇总_1113-1120.docx
```

`batch.json`可为组合对象数组或带 `portfolios` 的对象。schema：

```json
[{"name":"配置加力-四季均衡","inst":"中金财富","date":"2026-11-20","bench":"用户提供原文","reason":"有效理由","status":"","groups":{"固定收益":[["021151","广发景秀纯债C",0,18.18,"建仓"]],"分类缺失":[["968202","已核实名称",3,3,"持平"]]},"source_url":"详情页实际URL","strategy_id":"页面ID","adjustment_id":"调仓ID","source_count":2,"source_asset_totals":{"固定收益":18.18,"分类缺失":3},"notes":[]}]
```

权重单位为百分比，基金代码为字符串，操作第五项可省略。source_count必须是这份明细真实展示的数量，不能用列表数量冒充详情数量。`source_asset_totals`是页面调仓后合计，不是自行补算出的值。不足100%可暂存但必须通知用户，脚本绝不自动补差额。源数量不匹配则留在待核对清单，`append`不会写入该项，其他有效项继续。

追加结果给出added/skipped/pending/warnings。pending写入当周 `pending.json`；所有状态和来源保留在JSON，Word不含这些附加字段。用户对pending作出决定后在decisions.json保存日期、名称、ID、比较对象、用户原话；再将批准项单独形成batch并带 `--allow-same-weights` 追加，此标志仅用于用户明确批准的批次。

每次保存会在data旁的backups目录备份已有JSON和Word。替换失败时保留待修复的备份；检查文件后再继续。文件是本机路径，不要用已不存在的device_stage_files/device_commit_files等旧宿主工具。历史字体、页边距、表宽沿用生成器。

## 常规周起始周五复核

当用户要求上周五到本周五时，先用近七日读取并生成Word。起始上周五通常已在上期汇总，**先不自动追加该日**。生成后再查当天策略清单，保存 `boundary_review.json` 并在chat列出，等使用者点名。

记录字段建议为 `date`、`strategies`（名称、机构、ID、URL、`previous_match`、`decision`）。这些清单不是完整持仓，不应先写进portfolios或虚占编号。

用户明确批准某个起始周五策略后，才读取详情并形成仅包含批准项的batch。若明确允许上期已有条目补入本期，追加命令带 `--allow-previous-boundary`。脚本仅对**区间起始日且为周五**的候选忽略往期匹配；本期重复仍然拦截，其他日期仍然正常检查往期。常规append不带该参数，不改变原有跨期去重规则。

## 精简输出与总结

`preview`、`append`默认只输出编号、名称、原因、累计数量，不回显全部基金明细；完整记录仍在data.json或pending.json。只有排查具体问题时才加 `--verbose`。

用户要简短总结时先运行：

```bash
python3 SKILL/scripts/record_week.py summary --data /工作目录/指定区间/data.json
```

该摘要包括数量/日期/机构、缺项、前5名加减仓基金（排除货币、同基金份额按组合去重），以及剔除“策略成立”后的资产净变化。它是探索摘要，不替代对异常或复杂方向的具体操作核对。不要为简单总结先打印整个data.json或旧stats的全部组合明细。

没有上期文件时的 `boundary_review.json`：保留起始周五日期、完整策略名、机构及可用ID/URL，`previous_match` 为 `unknown`，`decision` 为 `pending`；在chat列出完整清单，让使用者逐项决定。不要生成虚假的上期匹配结果，也不要自动追加。
