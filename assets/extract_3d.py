# -*- coding: utf-8 -*-
"""
extract_3d.py —— 从「3D 元素幻灯片截图」里抠出元素本体，底色换成视频页的底色。

用法：
  python grid_sheet.py <素材目录>                 # 第一步：出网格验片，人工读框
  python extract_3d.py <素材目录> <输出目录>      # 第二步：按 OVERRIDES 抠图

关键设计（都是踩出来的，别改）：

1) 裁框只能人工给（OVERRIDES）
   自动定位全败：标题文字的边缘梯度比 3D 元素更强，任何"找最亮/最大连通域"的判据都会先选中标题。

2) 底色替换用「外圈环带常量偏移」，绝对不要做曲面拟合
   素材底色是「上亮下暗 + 顶部集中辉光」的非多项式形状：
     - 二次曲面拟合 → 中下部被抬高，底边过度扣除（实测 22~46% 像素被截断）
     - IRLS 迭代重拟合 → **下行失控**：拟合面越降越低，最后塌到 ≈0，残差图全亮，判据全废
   out = img − 外圈环带均值 + 目标底色，有界、不失控。

3) 目标底色必须与视频页 `.stage` 中部那段平地纯色完全一致
   抠图边缘与背景各半混色，两边底色不同就会看到一圈「接缝」。改页面底色就要回来改这里。

4) 末圈 12% 径向羽化压到纯底色，方便在页面里用 mask 融进背景，不露硬边。

5) 输出宽度默认 1800；进项目前建议降到 ~1200（解码开销，见 SKILL.md 性能一节）。
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

TARGET = np.array([0x0F, 0x1A, 0x28], dtype=np.float32) / 255.0   # = #0F1A28
OUT_W = 1800
PAD = 0.055          # 最终边界外扩比例
FEATHER = (0.72, 0.46)   # 径向羽化：r 超过 0.72 开始压，到 1.18 完全变纯底色

# 人工核定框：读 grid_sheet.py 产出的网格验片，把比例填进来。
# 命名规则取文件名最后一段（如 xxx_07.png → '07'）。缺项会退回窗口默认值，务必人工补。
OVERRIDES = {
    # '01': (0.04, 0.03, 0.54, 0.34),
    # '02': (0.30, 0.13, 0.82, 0.79),
    # ...
}


def ring_offset(img, ring=0.07):
    """外圈环带均值 → 常量背景偏移（有界，不会失控）"""
    H, W, _ = img.shape
    m = max(2, int(min(H, W) * ring))
    edge = np.concatenate([img[:m].reshape(-1, 3), img[-m:].reshape(-1, 3)])
    return edge.mean(0)


def feather_mask(shape):
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx / W - .5) * 2) ** 2 + ((yy / H - .5) * 2) ** 2)
    a, b = FEATHER
    return np.clip((r - a) / b, 0, 1)[..., None]


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    if not os.path.isdir(src):
        raise SystemExit('素材目录不存在：' + src)
    os.makedirs(out, exist_ok=True)

    files = sorted(glob.glob(os.path.join(src, '*.png')) + glob.glob(os.path.join(src, '*.jpg')))
    if not files:
        raise SystemExit('目录里没有 png/jpg：' + src)

    boxes, sheet_rows = {}, []
    for f in files:
        n = os.path.basename(f).rsplit('.', 1)[0].split('_')[-1]
        im = Image.open(f).convert('RGB')
        W, H = im.size
        if n not in OVERRIDES:
            print('⚠️  elem_%s 没有人工框，跳过（请先跑 grid_sheet.py 读框）' % n)
            continue
        box = OVERRIDES[n]
        boxes[n] = [round(float(v), 4) for v in box]

        x0, y0, x1, y1 = int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)
        if x1 - x0 < 16 or y1 - y0 < 16:
            print('⚠️  elem_%s 框太小，跳过' % n)
            continue
        c = im.crop((x0, y0, x1, y1))
        cw = OUT_W
        ch = int(c.height * cw / c.width)
        c = c.resize((cw, ch), Image.LANCZOS)
        a = np.asarray(c).astype(np.float32) / 255.0
        a = a - ring_offset(a) + TARGET
        k = feather_mask(a.shape[:2])
        res = np.clip(a * (1 - k) + TARGET * k, 0, 1)
        p = os.path.join(out, 'elem_%s.png' % n)
        Image.fromarray((res * 255).round().astype(np.uint8)).save(p)
        print('elem_%s  x%.3f-%.3f y%.3f-%.3f  ->  %dx%d' % (n, box[0], box[2], box[1], box[3], cw, ch))
        sheet_rows.append((n, im.resize((300, int(H * 300 / W)), Image.LANCZOS), box))

    json.dump(boxes, open(os.path.join(out, 'crop_boxes.json'), 'w'), ensure_ascii=False, indent=1)

    # 验片：左=框落在原片的位置，右=抠出的元素
    cols, cw, chh = 5, 300, 190
    rows_n = (len(sheet_rows) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cw, max(1, rows_n) * (chh + 22)), (12, 14, 20))
    d = ImageDraw.Draw(sheet)
    for i, (n, thumb, box) in enumerate(sheet_rows):
        x, y = (i % cols) * cw, (i // cols) * (chh + 22)
        sheet.paste(thumb, (x, y))
        tw, th = thumb.size
        d.rectangle([x + box[0] * tw, y + box[1] * th, x + box[2] * tw, y + box[3] * th],
                    outline=(255, 90, 90), width=2)
        e = Image.open(os.path.join(out, 'elem_%s.png' % n)).convert('RGB')
        e.thumbnail((cw - 8, chh - 26), Image.LANCZOS)
        sheet.paste(e, (x + (cw - e.width) // 2, y + 16 + (chh - 26 - e.height) // 2))
        d.text((x + 6, y + 2), 'elem_%s' % n, fill=(255, 220, 120))
    if sheet_rows:
        sheet.save(os.path.join(out, '定位验片.png'))
        print('\n验片 -> 定位验片.png（红框=裁框落点，右半=抠出结果）')
    if len(boxes) < len(files):
        print('还有 %d 张没抠 —— 缺 OVERRIDES' % (len(files) - len(boxes)))


if __name__ == '__main__':
    main()