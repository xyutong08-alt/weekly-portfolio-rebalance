#!/usr/bin/env python3
"""Prepare local font aliases and track pages actually reviewed. Standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fonts(args):
    work = args.workdir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    candidates = args.font_dir or [Path('/System/Library/Fonts'), Path('/Library/Fonts'),
                                  Path('/usr/share/fonts'), Path('/usr/local/share/fonts')]
    dirs = [p.resolve() for p in candidates if p.is_dir()]
    if not dirs:
        raise ValueError('未找到字体目录；用 --font-dir 指定当前环境的字体目录')
    root = ET.Element('fontconfig')
    for p in dirs:
        ET.SubElement(root, 'dir').text = str(p)
    ET.SubElement(root, 'cachedir').text = str(work / 'cache')
    config = work / 'fonts.conf'

    def save():
        ET.ElementTree(root).write(config, encoding='utf-8', xml_declaration=True)

    save()
    env = dict(os.environ, FONTCONFIG_FILE=str(config))
    proc = subprocess.run([str(args.fc_list), ':lang=zh', 'family'], env=env,
                          capture_output=True, text=True, timeout=30, check=True)
    families = {f.strip() for line in proc.stdout.splitlines() for f in line.split(',')}
    preferred = ['SimSun', 'STSong', 'Noto Serif CJK SC', 'Songti SC', 'Arial Unicode MS']
    family = next((f for f in preferred if f in families), None)
    if family is None:
        config.unlink()
        raise ValueError('未检测到支持的中文字体；保留Word字体，改用宿主原生预览或修复预览环境')
    if family != 'SimSun':
        alias = ET.SubElement(root, 'alias')
        ET.SubElement(alias, 'family').text = 'SimSun'
        ET.SubElement(ET.SubElement(alias, 'prefer'), 'family').text = family
        save()
    return {'fontconfig_file': str(config), 'preview_family': family,
            'config_sha256': digest(config), 'changes_word': False}


def pages(args):
    numbered = {}
    for p in args.images.glob('page-*.png'):
        match = re.fullmatch(r'page-(\d+)\.png', p.name)
        if match:
            numbered[int(match[1])] = p
    if not numbered or sorted(numbered) != list(range(1, max(numbered) + 1)):
        raise ValueError('预览页必须是从page-1.png开始的连续页；检查目录和渲染结果')
    approved = set(args.approve_pages or [])
    if not approved.issubset(numbered):
        raise ValueError('指定的已检查页号不在本次预览中')
    font_file = os.environ.get('FONTCONFIG_FILE')
    context = {'renderer': args.context,
               'fontconfig_sha256': digest(font_file) if font_file else None}
    old = json.loads(args.manifest.read_text(encoding='utf-8')) if args.manifest.exists() else {}
    previous = old.get('pages', {}) if old.get('context') == context else {}
    current, to_review, reused = {}, [], []
    for number, p in sorted(numbered.items()):
        sha = digest(p)
        prior = previous.get(str(number), {})
        reuse = prior.get('reviewed') is True and prior.get('sha256') == sha
        reviewed = number in approved or reuse
        current[str(number)] = {'sha256': sha, 'reviewed': reviewed}
        if not reviewed:
            to_review.append(number)
        elif reuse and number not in approved:
            reused.append(number)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    payload = {'context': context, 'pages': current}
    temporary = args.manifest.with_suffix(args.manifest.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, args.manifest)
    return {'page_count': len(current), 'to_review': to_review, 'reused': reused,
            'approved_now': sorted(approved), 'all_reviewed': not to_review}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    f = sub.add_parser('fonts')
    f.add_argument('--workdir', type=Path, required=True)
    f.add_argument('--fc-list', type=Path, required=True)
    f.add_argument('--font-dir', type=Path, action='append')
    p = sub.add_parser('pages')
    p.add_argument('--images', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--context', required=True)
    p.add_argument('--approve-pages', type=int, nargs='+')
    args = parser.parse_args()
    try:
        result = fonts(args) if args.command == 'fonts' else pages(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
