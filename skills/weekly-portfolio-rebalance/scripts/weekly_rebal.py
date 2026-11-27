"""weekly_rebal —— 投顾组合「本周调仓汇总」docx 生成与检查工具（单文件、零依赖，只用 Python 标准库）。

数据文件（JSON）格式：
{
  "start": "2026.11.06", "end": "2026.11.13",
  "portfolios": [
    {"name": "配置加力-四季均衡", "inst": "中金财富",
     "bench": "中证800指数 × 20% ＋ 中债-综合全价（总值）指数 × 80%",   # null=不写基准行；""=写“（待补充）”
     "date": "2026-11-06",
     "reason": "根据策略信号和风控管理，……",                         # 通用理由会在生成时自动去掉
     "status": "",                                                   # 可选，如 "已停止"（只用于提醒，不写进文档）
     "groups": {"权益": [["020957", "中银全球策略(QDII-FOF)C", 8, 6]],
                "固定收益": [["021151", "广发景秀纯债C", 0, 18.18]]}}  # 第5个元素可强制操作标签，如 "减仓"
  ]
}

命令：
  python3 weekly_rebal.py check  data.json [上周.docx ...]   # 规则检查：跳过机构、多期系列、重复、缺基准、合计异常
  python3 weekly_rebal.py build  data.json out.docx          # 生成 docx（不需要模板）
  python3 weekly_rebal.py import 某周.docx > data.json         # 从已交付的 docx 反解出数据（断点续做用）
  python3 weekly_rebal.py stats  data.json                   # 周总结用：加仓次数排行、方向统计、日期分布
"""
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from xml.sax.saxutils import escape

# ============================================================ 规则（和用户逐条确认过）
SKIP_INST = ["中欧", "华宝", "盈米", "且慢", "国联证券", "国投证券", "山西证券"]   # 机构名包含即跳过
GENERIC_REASONS = {
    "动态优化再平衡", "根据最近的市场情况,查理对组合进行了资产配置调整", "根据最近的市场情况，查理对组合进行了资产配置调整",
    "组合调仓", "无", "根据投资观点，结合组合基准进行再平衡调仓", "季度定期再平衡", "优化组合中的基金持仓", "持仓产品优化",
    "底层基金优化", "根据模型信号及市场行情特征进行优化", "调整基金品种选择", "根据市场情况调整组合持仓",
    "根据市场情况和风格变化调整组合持仓", "优化持有基金结构", "调整资产配置结构", "优化资产配置结构", "组合策略调整",
    "优选部分基金，调整组合持仓", "优化持仓", "优化持仓基金", "组合调仓，对部分持仓基金进行调整，优化持仓结构",
}
OP_ORDER = {"建仓": 0, "加仓": 1, "持平": 2, "减仓": 3, "清仓": 4}

# ============================================================ 样式
RED, GREEN, GRAY, NAVY, BLACK, DARK = "C00000", "00B050", "7F7F7F", "1F3864", "000000", "404040"
W = [960, 3446, 700, 1000, 1000, 1200]                     # 表格列宽（dxa）
OPC = {"建仓": RED, "加仓": RED, "持平": GRAY, "减仓": GREEN, "清仓": GREEN}


def calc_op(b, a):
    return "持平" if a == b else "建仓" if b == 0 else "清仓" if a == 0 else "加仓" if a > b else "减仓"


def rows_of(p):
    """[(资产, 代码, 名称, 操作, 前, 后)]"""
    out = []
    for asset, fs in p["groups"].items():
        for f in fs:
            out.append((asset, f[0], f[1], f[4] if len(f) > 4 else calc_op(f[2], f[3]), float(f[2]), float(f[3])))
    return out


def norm_reason(r):
    return re.sub(r"[。．.\s]+$", "", (r or "").strip())


def is_generic(r):
    return norm_reason(r) in {norm_reason(g) for g in GENERIC_REASONS}


def full_name(p):
    return f"{p['name']}（{p['inst']}）" if p.get("inst") else p["name"]


def signature(p):
    """同一套权重的指纹：基金名(去A/C份额后缀) + 调整前后权重。用来抓“换个名字/ID的同一组合”。"""
    return frozenset((re.sub(r"(A|C|E|D|I|B|A/E|C类|A类)$", "", r[2]), round(r[4], 2), round(r[5], 2)) for r in rows_of(p))


# ============================================================ docx 生成（手写 WordprocessingML，无需模板）
def _run(t, sz=18, bold=False, color=BLACK):
    b = "<w:b/><w:bCs/>" if bold else ""
    return (f'<w:r><w:rPr><w:rFonts w:ascii="SimSun" w:eastAsia="SimSun" w:hAnsi="SimSun" w:cs="SimSun" w:hint="eastAsia"/>{b}'
            f'<w:color w:val="{color}"/><w:kern w:val="0"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(t)}</w:t></w:r>')


def _para(runs, jc="left", before=0, after=40, keep=False):
    k = "<w:keepNext/>" if keep else ""
    return (f'<w:p><w:pPr>{k}<w:widowControl/><w:spacing w:before="{before}" w:after="{after}" w:line="300" w:lineRule="auto"/>'
            f'<w:jc w:val="{jc}"/></w:pPr>{"".join(runs)}</w:p>')


def _info(label, text):
    return _para([_run(label, bold=True, color=DARK), _run(text)], keep=True)


def _cell(w, runs, jc="center", fill=None, border="D9D9D9", span=None):
    s = f'<w:gridSpan w:val="{span}"/>' if span else ""
    f = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
    bd = "".join(f'<w:{e} w:val="single" w:sz="4" w:space="0" w:color="{border}"/>' for e in ("top", "left", "bottom", "right"))
    return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{s}<w:tcBorders>{bd}</w:tcBorders>{f}<w:vAlign w:val="center"/></w:tcPr>'
            f'<w:p><w:pPr><w:widowControl/><w:spacing w:before="40" w:after="40"/><w:jc w:val="{jc}"/></w:pPr>{"".join(runs)}</w:p></w:tc>')


def _pct(v):
    return f"{v:.2f}%"


def _signed(v):
    return "0.00%" if abs(v) < 1e-9 else f"{v:+.2f}%"


def _table(p):
    hdr = ["基金代码", "基金名称", "操作", "调整前", "调整后", "权重变化"]
    rows = ['<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>' + "".join(
        _cell(W[i], [_run(h, bold=True, color="FFFFFF")], fill="4472C4", border="4472C4") for i, h in enumerate(hdr)) + "</w:tr>"]
    by = defaultdict(list)
    for r in rows_of(p):
        by[r[0]].append(r)
    for asset, fs in by.items():
        tot = sum(f[5] for f in fs)
        rows.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + _cell(sum(W), [_run(asset, bold=True, color=NAVY),
                    _run(f"　　调仓后合计 {_pct(tot)}", color=NAVY)], jc="left", fill="D9E2F3", span=6) + "</w:tr>")
        for _, c, n, op, b, a in sorted(fs, key=lambda f: (OP_ORDER[f[3]], -abs(f[5] - f[4]))):
            col, strong = OPC[op], op != "持平"
            rows.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + _cell(W[0], [_run(c)]) + _cell(W[1], [_run(n)], jc="left")
                        + _cell(W[2], [_run(op, bold=strong, color=col)]) + _cell(W[3], [_run(_pct(b))])
                        + _cell(W[4], [_run(_pct(a))]) + _cell(W[5], [_run(_signed(a - b), bold=strong, color=col)]) + "</w:tr>")
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in W)
    return (f'<w:tbl><w:tblPr><w:tblW w:w="{sum(W)}" w:type="dxa"/><w:jc w:val="center"/><w:tblLayout w:type="fixed"/>'
            f'<w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr>'
            f'<w:tblGrid>{grid}</w:tblGrid>{"".join(rows)}</w:tbl>')


def _block(no, p):
    out = [_para([_run(f"{no}、{full_name(p)}", sz=22, bold=True, color=NAVY)], before=360, after=120, keep=True)]
    if p.get("bench") is not None:
        out.append(_info("策略业绩基准：", p["bench"] or "（待补充）"))
    out.append(_info("调仓日期：", p["date"]))
    reason = (p.get("reason") or "").strip()
    if reason and not is_generic(reason):
        out.append(_info("调仓理由：", reason))
    out.append(_para([_run("")], after=60, keep=True))
    out.append(_table(p))
    out.append(_para([_run("")], after=120))
    return "".join(out)


_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
       '<Default Extension="xml" ContentType="application/xml"/>'
       '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
       '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
_DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
_STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {_NS}><w:docDefaults><w:rPrDefault><w:rPr>'
           '<w:rFonts w:ascii="SimSun" w:eastAsia="SimSun" w:hAnsi="SimSun" w:cs="SimSun"/><w:sz w:val="18"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/>'
           '</w:rPr></w:rPrDefault><w:pPrDefault/></w:docDefaults>'
           '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:widowControl w:val="0"/><w:jc w:val="both"/></w:pPr></w:style>'
           '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/>'
           '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
           '</w:styles>')


def build(data, out):
    ps = data["portfolios"]
    title = f"投顾组合调仓汇总（{data['start']} – {data['end']}）"
    body = [_para([_run(title, sz=32, bold=True, color=NAVY)], jc="center", after=120),
            _para([_run(f"一共{len(ps)}个组合", sz=20, color=GRAY)], jc="center", after=120)]
    body += [_block(i, p) for i, p in enumerate(ps, 1)]
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1800" w:bottom="1440" w:left="1800" '
            'w:header="851" w:footer="992" w:gutter="0"/><w:cols w:space="425"/><w:docGrid w:type="lines" w:linePitch="312"/></w:sectPr>')
    doc = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_NS}><w:body>{"".join(body)}{sect}</w:body></w:document>'
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/_rels/document.xml.rels", _DOC_RELS)
        z.writestr("word/styles.xml", _STYLES)
        z.writestr("word/document.xml", doc)
    return len(ps)


# ============================================================ 从 docx 反解数据
def import_docx(path):
    x = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    body = x[x.index("<w:body>"):]
    items = re.findall(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>", body, re.S)

    def text(s):
        return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", s)).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    data = {"start": "", "end": "", "portfolios": []}
    cur = None
    for it in items:
        if it.startswith("<w:tbl"):
            if cur is None:
                continue
            asset = None
            for tr in re.findall(r"<w:tr[ >].*?</w:tr>", it, re.S):
                cells = [text(tc) for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)]
                if len(cells) == 1:
                    asset = re.split(r"\s|　", cells[0])[0]
                    cur["groups"].setdefault(asset, [])
                elif len(cells) == 6 and cells[0] != "基金代码":
                    b, a = float(cells[3].rstrip("%")), float(cells[4].rstrip("%"))
                    row = [cells[0], cells[1], b, a]
                    if cells[2] != calc_op(b, a):
                        row.append(cells[2])
                    cur["groups"][asset].append(row)
            continue
        t = text(it).strip()
        m = re.match(r"投顾组合调仓汇总（(.+?)\s*–\s*(.+?)）", t)
        if m:
            data["start"], data["end"] = m.group(1), m.group(2)
            continue
        m = re.match(r"^(\d+)、(.+)$", t)
        if m:
            nm = m.group(2)
            mi = re.match(r"^(.*)（([^（）]+)）$", nm)
            cur = {"name": mi.group(1) if mi else nm, "inst": mi.group(2) if mi else "", "bench": None,
                   "date": "", "reason": "", "groups": {}}
            data["portfolios"].append(cur)
        elif cur is not None and t.startswith("策略业绩基准："):
            v = t[len("策略业绩基准："):]
            cur["bench"] = "" if v == "（待补充）" else v
        elif cur is not None and t.startswith("调仓日期："):
            cur["date"] = t[len("调仓日期："):]
        elif cur is not None and t.startswith("调仓理由："):
            cur["reason"] = t[len("调仓理由："):]
    return data


def load(path):
    return import_docx(path) if path.endswith(".docx") else json.load(open(path, encoding="utf-8"))


# ============================================================ 规则检查
def check(data, prev_paths=()):
    ps = data["portfolios"]
    msgs = []
    for i, p in enumerate(ps, 1):
        fn = f"#{i} {full_name(p)}"
        hit = [k for k in SKIP_INST if k in (p.get("inst") or "")]
        if hit:
            msgs.append(("删除", f"{fn}：属于不收录机构（{hit[0]}），应删除并告诉用户"))
        if re.search(r"第?[一二三四五六七八九十\d]+期|\d+期$", p["name"]):
            msgs.append(("确认", f"{fn}：名称带期数。多期系列只留一期且去掉期数；若同系列已收录则不加"))
        if p.get("bench") == "":
            msgs.append(("缺", f"{fn}：缺策略业绩基准（文档显示“待补充”）"))
        if not p.get("date"):
            msgs.append(("缺", f"{fn}：缺调仓日期"))
        if p.get("status"):
            msgs.append(("提示", f"{fn}：状态为“{p['status']}”"))
        for asset, fs in p["groups"].items():
            for f in fs:
                if len(f) > 4 and f[4] != calc_op(f[2], f[3]):
                    msgs.append(("提示", f"{fn}：{f[1]} 页面标“{f[4]}”，但权重 {f[2]}→{f[3]}，已按页面标签记"))
        tot = sum(r[5] for r in rows_of(p))
        if abs(tot - 100) > 1.5:
            msgs.append(("核对", f"{fn}：调仓后合计 {tot:.2f}%，可能截图漏了基金"))
    # 本周内重复
    seen_nd, seen_sig = {}, {}
    for i, p in enumerate(ps, 1):
        k = (p["name"], p["date"])
        if k in seen_nd:
            msgs.append(("重复", f"#{i} {full_name(p)} 与 #{seen_nd[k]} 同名同日期，删掉后一个"))
        seen_nd.setdefault(k, i)
        s = signature(p)
        if s in seen_sig:
            msgs.append(("问用户", f"#{i} {full_name(p)} 与 #{seen_sig[s]} {full_name(ps[seen_sig[s]-1])} 权重完全相同（换名/换ID？），问用户加不加"))
        seen_sig.setdefault(s, i)
    # 与往周重复
    for path in prev_paths:
        old = load(path)["portfolios"]
        o_nd = {(o["name"], o["date"]) for o in old}
        o_sig = {signature(o): full_name(o) for o in old}
        for i, p in enumerate(ps, 1):
            if (p["name"], p["date"]) in o_nd:
                msgs.append(("重复", f"#{i} {full_name(p)}（{p['date']}）上周文档已有，不加"))
            elif signature(p) in o_sig:
                msgs.append(("重复", f"#{i} {full_name(p)} 与上周 {o_sig[signature(p)]} 权重完全相同，不加并告诉用户"))
    if not msgs:
        print("OK：没有发现问题")
    for lv, m in msgs:
        print(f"[{lv}] {m}")
    return msgs


# ============================================================ 周总结统计
def stats(data):
    ps = data["portfolios"]
    print(f"组合数：{len(ps)}")
    print("调仓日期分布：", dict(sorted(Counter(p["date"] for p in ps).items())))
    print("机构分布：", Counter(p["inst"] for p in ps).most_common())
    key = lambda n: re.sub(r"(A|C|E|D|I|B|A/E|C类|A类)$", "", n)
    add, cut, fam = Counter(), Counter(), defaultdict(list)
    asset_chg = defaultdict(float)
    for p in ps:
        for asset, c, n, op, b, a in rows_of(p):
            asset_chg[asset] += a - b
            if op in ("建仓", "加仓"):
                add[key(n)] += 1
            if op in ("减仓", "清仓"):
                cut[key(n)] += 1
            fam[key(n)].append(f"{p['name']}:{op}{b:g}→{a:g}")
    print("\n被建仓/加仓次数最多（含货币基金，回答时货基单独说明）：")
    for n, k in add.most_common(10):
        print(f"  {k}次  {n}  | {'；'.join(fam[n])}")
    print("\n被减仓/清仓次数最多：")
    for n, k in cut.most_common(10):
        print(f"  {k}次  {n}  | {'；'.join(fam[n])}")
    print("\n各大类权重变化合计（百分点，所有组合简单相加，只看方向）：", {k: round(v, 2) for k, v in asset_chg.items()})


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "build":
        n = build(load(args[0]), args[1])
        print(f"已生成 {args[1]}，一共{n}个组合")
    elif cmd == "check":
        check(load(args[0]), args[1:])
    elif cmd == "import":
        json.dump(import_docx(args[0]), sys.stdout, ensure_ascii=False, indent=1)
    elif cmd == "stats":
        stats(load(args[0]))
    else:
        print(__doc__)
