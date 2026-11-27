#!/usr/bin/env python3
"""Local JSON + Word persistence. Browser extraction remains with the host UI tools."""
import argparse
import contextlib
import copy
import datetime as dt
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile
import weekly_rebal as w


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def dump(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def signature(p):
    # Code identifies the displayed share class; remove only irrelevant zero rows.
    return tuple(sorted((str(f[0]), round(float(f[2]), 4), round(float(f[3]), 4))
                        for rows in p['groups'].values() for f in rows if f[2] or f[3]))


def key(p):
    return p['name'], p['inst'], p['date']


def validate(p):
    for k in ('name', 'inst', 'date', 'groups', 'bench'):
        if k not in p:
            raise ValueError('缺少字段：' + k)
    if not isinstance(p['name'], str) or not p['name'].strip() or not isinstance(p['inst'], str) or not p['inst'].strip():
        raise ValueError('名称和机构不能为空')
    dt.date.fromisoformat(p['date'])
    if p['bench'] is not None and not isinstance(p['bench'], str):
        raise ValueError('bench仅可为字符串或null')
    if not isinstance(p['groups'], dict) or not any(p['groups'].values()):
        raise ValueError('没有基金明细')
    codes = []
    for asset, rows in p['groups'].items():
        if not isinstance(asset, str) or not asset.strip() or not isinstance(rows, list):
            raise ValueError('资产分组不合法')
        for f in rows:
            if len(f) not in (4, 5) or not isinstance(f[0], str) or not re.fullmatch(r'\d{6}', f[0]):
                raise ValueError('基金代码应为6位字符串，基金行应为4或5项')
            if not isinstance(f[1], str) or not f[1].strip():
                raise ValueError('基金名称不能为空')
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 100 for v in f[2:4]):
                raise ValueError('权重应为0至100的有限数值')
            if len(f) == 5 and f[4] not in w.OP_ORDER:
                raise ValueError('未知操作标签')
            codes.append(f[0])
    if len(codes) != len(set(codes)):
        raise ValueError('同一组合内基金代码重复，请核对截图重叠')
    if p.get('source_count') is not None and p['source_count'] != len(codes):
        raise ValueError(f"源页面{p['source_count']}只，已读{len(codes)}只，先补齐明细")
    for a, expected in p.get('source_asset_totals', {}).items():
        actual = sum(f[3] for f in p['groups'].get(a, []))
        if not isinstance(expected, (float, int)) or abs(actual - expected) > .1:
            raise ValueError(f'资产组{a}与源页面合计不符：{actual:.2f} / {expected}')


def prepare(data, batch, previous, allow_same_weights=False):
    result = dict(added=[], skipped=[], pending=[], warnings=[])
    existing = list(data['portfolios'])
    old = [p for path in previous for p in w.load(str(path))['portfolios']]
    for raw in batch:
        p = copy.deepcopy(raw)
        label = str(p.get('name', '未命名'))
        if any(x in str(p.get('inst', '')) for x in w.SKIP_INST):
            result['skipped'].append(dict(name=label, reason='排除机构', portfolio=p))
            continue
        try:
            validate(p)
            if not data['start'].replace('.', '-') <= p['date'] <= data['end'].replace('.', '-'):
                raise ValueError('调仓日期不在当周区间')
        except (ValueError, TypeError, KeyError) as e:
            result['pending'].append(dict(name=label, reason=str(e), portfolio=p))
            continue
        peers = existing + old
        same = next((o for o in peers if key(o) == key(p) or (p.get('adjustment_id') and o.get('adjustment_id') == p['adjustment_id'])), None)
        if same:
            result['skipped'].append(dict(name=label, reason='同组合同日期或同调仓ID已有', portfolio=p))
            continue
        if re.search(r'第?[一二三四五六七八九十\d]+期', p['name']):
            result['pending'].append(dict(name=label, reason='请按系列规则去期数，只留一期后重试', portfolio=p))
            continue
        duplicate = next((o for o in peers if signature(o) == signature(p)), None)
        if duplicate and not allow_same_weights:
            result['pending'].append(dict(name=label, reason='同权重需用户确认', compare_to=duplicate['name'], portfolio=p))
            continue
        reason = re.sub(r'^调仓原因[：:]\s*', '', p.get('reason') or '').strip()
        p['reason'] = '' if reason == '调仓' or w.is_generic(reason) or reason.rstrip('。') == '资产配置结构优化' else reason
        p.setdefault('status', '')
        total = sum(f[3] for rows in p['groups'].values() for f in rows)
        if abs(total - 100) > .15:
            result['warnings'].append(dict(name=label, reason=f'合计{total:.2f}%，请先核对分类缺失组；未自动补足'))
        for asset, rows in p['groups'].items():
            for f in rows:
                if len(f) == 5 and f[4] != w.calc_op(f[2], f[3]):
                    result['warnings'].append(dict(name=label, reason=f'{f[0]}页面标签与权重矛盾，已保留标签'))
        if p['bench'] == '':
            result['warnings'].append(dict(name=label, reason='基准待补充'))
        existing.append(p)
        result['added'].append(dict(number=len(existing), name=label, portfolio=p))
    updated = copy.deepcopy(data)
    updated['portfolios'] = existing
    return updated, result


def commit(data_path, out_path, data):
    data_path, out_path = Path(data_path), Path(out_path)
    if data_path.resolve() == out_path.resolve():
        raise ValueError('JSON和Word不能使用同一路径')
    for p in (data_path, out_path):
        p.parent.mkdir(parents=True, exist_ok=True)
    backup = data_path.parent / 'backups' / dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup.mkdir(parents=True)
    originals = {p: p.read_bytes() if p.exists() else None for p in (data_path, out_path)}
    for i, (p, content) in enumerate(originals.items()):
        if content is not None:
            (backup / (str(i) + '_' + p.name)).write_bytes(content)
    tmp_json = tmp_doc = None
    try:
        with tempfile.NamedTemporaryFile(dir=data_path.parent, suffix='.json', delete=False) as f:
            tmp_json = Path(f.name)
        with tempfile.NamedTemporaryFile(dir=out_path.parent, suffix='.docx', delete=False) as f:
            tmp_doc = Path(f.name)
        dump(tmp_json, data)
        w.build(data, str(tmp_doc))
        restored = w.import_docx(str(tmp_doc))
        if (restored['start'], restored['end']) != (data['start'], data['end']) or len(restored['portfolios']) != len(data['portfolios']):
            raise ValueError('Word往返数量或区间校验失败')
        for a, b in zip(data['portfolios'], restored['portfolios']):
            if (a['name'], a.get('inst'), a['date'], a['bench']) != (b['name'], b.get('inst'), b['date'], b['bench']) or sorted(w.rows_of(a)) != sorted(w.rows_of(b)):
                raise ValueError('Word往返数据校验失败：' + a['name'])
        os.replace(tmp_doc, out_path)
        os.replace(tmp_json, data_path)
    except Exception:
        for p, content in originals.items():
            if content is not None:
                p.write_bytes(content)
            elif p.exists():
                p.unlink()
        raise
    finally:
        for p in (tmp_json, tmp_doc):
            if p is not None and p.exists():
                p.unlink()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['init', 'preview', 'append'])
    ap.add_argument('--data', required=True, type=Path)
    ap.add_argument('--end')
    ap.add_argument('--from-docx', type=Path)
    ap.add_argument('--batch', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--previous', nargs='*', default=[], type=Path)
    ap.add_argument('--allow-same-weights', action='store_true')
    a = ap.parse_args()
    if a.command == 'init':
        if a.data.exists():
            raise ValueError('已有JSON，继续使用；拒绝覆盖初始化')
        if a.from_docx:
            data = w.import_docx(str(a.from_docx))
        else:
            if not a.end:
                raise ValueError('请提供本周五 --end 或 --from-docx')
            end = dt.date.fromisoformat(a.end)
            if end.weekday() != 4:
                raise ValueError('--end必须是周五')
            data = dict(start=(end-dt.timedelta(days=7)).strftime('%Y.%m.%d'), end=end.strftime('%Y.%m.%d'), portfolios=[])
        a.data.parent.mkdir(parents=True, exist_ok=True)
        dump(a.data, data)
        print(json.dumps(dict(data=str(a.data), count=len(data['portfolios'])), ensure_ascii=False))
        return
    if not a.batch:
        raise ValueError('需要 --batch')
    batch = read(a.batch)
    if isinstance(batch, dict):
        batch = batch['portfolios']
    if not isinstance(batch, list):
        raise ValueError('batch应为数组或含portfolios的对象')
    data, result = prepare(read(a.data), batch, a.previous, a.allow_same_weights)
    if a.command == 'append':
        if not a.out:
            raise ValueError('需要 --out')
        if result['added']:
            commit(a.data, a.out, data)
        pending = a.data.parent/'pending.json'
        saved = read(pending) if pending.exists() else []
        saved.extend(x for x in result['pending'] if x not in saved)
        if saved:
            dump(pending, saved)
    result['total'] = len(data['portfolios'])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
