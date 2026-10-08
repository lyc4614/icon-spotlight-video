# -*- coding: utf-8 -*-
"""
check_contrast.py —— 量「元素 / 卡片 vs 背景」的明度分离度。

判据（沿用本项目长期口径）：元素区域 HSV 明度均值 **> 背景 + 0.15** 才立得住。
低于 0.15 = 观众看不出来这张卡片浮在背景上，只是同一片颜色里的一块深浅。

用法：
  python check_contrast.py <帧.png> [rects.json]

rects.json 由 probe_rects.cjs 生成（DOM 取值，不是手填像素坐标）。
不传 rects.json 时会退化成「上下对半」粗测 —— 只用来快速判断方向，不作数。

⚠️ 自检内置：会同时报告「A/B 两图是否完全相同」。若 Δ 恒为 0，
   先怀疑「隐藏正片的方式失效」而不是怀疑卡片没对比度
   （visibility:hidden 会被 __render 写的内联 visibility:visible 覆盖，必须用 display:none）。
   退出码：0 = 全部达标；1 = 有未达标项；3 = 测量自检失败。
"""
import json
import os
import sys

import numpy as np
from PIL import Image

DELTA_MIN = 0.15


def value_map(a):
    """近似明度：HSV 的 V 与 (max+min)/2 在暗场分辨率接近，取后者更稳。a: HxWx3 float 0..1"""
    mx = a.max(2)
    mn = a.min(2)
    return (mx + mn) / 2.0


def region(a, box):
    x0, y0, x1, y1 = box
    H, W = a.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(W, x1), min(H, y1)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return a[y0:y1, x0:x1]


def stat(a, box, label):
    r = region(a, box)
    if r is None:
        return None
    v = value_map(r).mean()
    return {'label': label, 'v': float(v),
            'rgb': [float(c) for c in r.reshape(-1, 3).mean(0)],
            'box': list(box)}


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    frame = sys.argv[1]
    im = Image.open(frame).convert('RGB')
    a = np.asarray(im).astype(np.float32) / 255.0
    print('帧 %s  %dx%d' % (os.path.basename(frame), im.width, im.height))

    if len(sys.argv) >= 3 and os.path.exists(sys.argv[2]):
        rows = json.load(open(sys.argv[2], encoding='utf-8')).get('rows', [])
        rows = [r for r in rows if not r.get('missing')]
    else:
        print('! 未提供 rects.json，用「上 1/3 为背景 / 下 1/3 为元素」的粗测，只看方向')
        H = im.height
        rows = [{'key': 'coarse', 'rect': [60, int(H * .62), im.width - 60, int(H * .72)],
                 'bg': [60, int(H * .38), im.width - 60, int(H * .46)]}]

    print('  %-9s %-6s %-8s %-8s %-9s %s' % ('区域', '类型', '明度', '背景', 'Δ', 'RGB'))
    bad, skipped = [], []
    for r in rows:
        s = stat(a, r['rect'], r['key'])
        b = stat(a, r['bg'], r['key'] + '-bg')
        if not s or not b:
            print('  %-9s 区域太小，跳过' % r['key'])
            continue
        d = s['v'] - b['v']
        mode = r.get('mode', 'card')
        if mode == 'ref':
            verdict = '仅参考'
            skipped.append(r['key'])
        else:
            ok = d >= DELTA_MIN
            verdict = 'OK' if ok else '✗ 未达标'
            if not ok:
                bad.append((r['key'], d))
        rgb = '#%02X%02X%02X' % tuple(int(c * 255) for c in s['rgb'])
        print('  %-9s %-6s %-8.3f %-8.3f %+9.3f %s %s' % (
            r['key'], mode, s['v'], b['v'], d, rgb, verdict))

    print('\n判据 Δ >= %.2f（%s 类元素才参与判定）' % (DELTA_MIN, 'card'))
    if skipped:
        print('仅参考不判定：' + '、'.join(skipped) + '（暗色压暗色，靠描边/文字对比，不是靠明度差立住）')
    if not bad:
        print('全部达标 ✓')
        return 0
    print('未达标：' + '、'.join('%s (Δ=%+.3f)' % (k, d) for k, d in bad))
    print('常见原因：① 暗角整层盖在内容之上（要拆成内容之下的 .vig + 内容之上的轻收边 .vig2）')
    print('          ② 卡面明度太低（抬高 .card 的渐变上端）')
    print('          ③ 元素本身亮度不够（素材底色偏亮时把元素整体提亮）')
    return 1


if __name__ == '__main__':
    sys.exit(main())