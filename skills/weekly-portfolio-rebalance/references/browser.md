# 网页读取（按需阅读）

## 入口与登录

- 用户指定的入口：`https://strategy1.post.advisorplanet.cn/adminweb/strategy-library`（策略库）。首次执行从此处进入；若用户已打开同站点并登录，直接复用现有tab。
- 检查登录状态。遇到登录页、账号密码、短信验证码、邮箱验证码或图形验证码时，把页面交给使用者，说明“请在网页中完成登录和验证码，完成后我继续整理”。默认让使用者直接在网页填写，不要求把密码或验证码发到聊天，不把它们写进技能、脚本或数据文件，不自动绕过验证。
- 使用者完成后，重新读取当前页面，确认已进入已登录的策略库或其他同站业务页，再继续。不以等待时间代替登录成功证据；会话过期时按同一流程交接。
- 登录后通过页面导航进入“调仓动态”，已知页面为 `https://strategy1.post.advisorplanet.cn/adminweb/adjustment-feed`。先确认页面提供该入口；可复用本轮已观察过的URL。策略库用于查找完整策略详情和基准，调仓动态用于按日期覆盖全部调仓记录。
- 登录访问仅用于用户请求的查询与本地记录，不更改账号设置、关注、对比或实际策略配置。网页登录不会随分享包转移，每位使用者使用自己的获授权账号。


使用宿主当前提供的浏览器工具及其文档（此环境为 `mcp__cua_repl.js`）。先绑定用户打开的tab，别重复新建或刷新。不能把此前工具的tab对象或AX数字索引当作永久配置。接口只有在当前工具真实提供且用户授权时才能使用；本技能默认通过已登录网页的可见DOM读取，不是后台API爬虫或定时任务。

## 覆盖和详情核对

1. 读日期分组、分页数、当前页。可适度增加每页数量；看完目标日期后，检查前后页，避免同一天跨页漏记。过滤排除机构后再展开候选。
2. 每个候选展开完整理由与全部变动；保存结构化数据。接着点击该候选标题进入详情，核对完整名称、机构、日期、ID、基准、状态、顶部理由与ID下灰字，以及全部基金行。详情数量可能少于列表：例如列表含0→0行；记录差异，绝不把不全的列表六行当全量。
3. 导航后先确认路径与新策略标题/ID对应，检查不再是加载占位、过期标题；已出现基准不代表其他区块都完成加载。每次读出的名称、基准与基金表要来自**同一个已确认页面**。只有完成提取及备份后才返回列表。
4. 返回列表常重置为第1页10条/页。重新观察后导航目标日期，不沿用旧位置、旧nth索引或AX索引。DOM定位超时但节点存在时，观察截图/AX找遮挡或滚动问题再换定位；不盲目重试。
5. 分批保存数据，不在浏览器变量里攒整周再一次写文件。遵守CUA的读写边界和completion_summary要求，不在浏览器控制环境私自读写本地文件、调用隐藏状态、网络fetch或认证存储。

## 已观察过的DOM结构（每次先确认仍存在）

列表：`.feed-day-group .feed-day-label`为日期；`.feed-record-card`为组合卡片；`.record-strategy-name strong`为名称；`.institution-name`为机构；`.strategy-reason`为理由。

完整表在`.asset-fund-group`，组名位于`.asset-fund-group-header .asset-tag`；基金行`.fund-change-row`，代码`.fund-name small`，名称`.fund-name`（去代码），标签`.change-tag`，权重`strong`。详情也曾复用此表结构。对每个组遍历，不白名单限定“权益/固定收益/货币/其他”，必须保留“分类缺失”和将来新组名。

示意只读提取函数（放入文档支持的`tab.playwright.evaluate`；先观察当前DOM确认结构）：

```javascript
() => Array.from(document.querySelectorAll('.asset-fund-group')).map(g => ({
  asset: g.querySelector('.asset-fund-group-header .asset-tag').innerText,
  source_total: g.querySelector('.asset-fund-group-header strong').innerText,
  rows: Array.from(g.querySelectorAll('.fund-change-row')).map(r => {
    const el = r.querySelector('.fund-name');
    const code = el.querySelector('small').innerText.trim();
    const v = r.querySelector('strong').innerText.match(/[\d.]+/g).map(Number);
    return [code, el.innerText.replace(code, '').trim(), v[0], v[1] ?? v[0], r.querySelector('.change-tag').innerText.trim()];
  })
}))
```

详情`.summary-title`曾为标题；用实际页面可见的“策略业绩基准：”文本提取基准，剔除其后的行情不完整提示。这些选择器是经验线索，改版时读取新DOM调整，不能凭空猜接口地址、策略ID或URL。只输出需要的区块，避免整个业绩历史反复消耗token。
