# -*- coding: utf-8 -*-
"""
grid_sheet.py —— 生成「带 5% 坐标网格」的放大验片，用来【人工读裁框】。

为什么必须人工读框（别再写自动定位了）：
  这类素材是「一张 16:9 幻灯片截图里放一个 3D 元素 + 若干标注文字」。
  四种自动判据全试过、全败，原因是同一个 —— **标题文字的边缘梯度比 3D 元素更强**
  （文字是硬边，3D 渲染是软光），任何"找最亮/最有结构/最大连通域"的算法都会先选中标题。
  试过的失败路径见 SKILL.md 的「素材抠图」一节。

用法：
  python grid_sheet.py <素材片目录> [输出目录]

产出：网格验片_1.png ...（2x2 每张，10% 处带百分比标注，20% 粗线）
读出框后把比例写进 extract_3d.py 的 OVERRIDES。
"""
import glob
import os
import sys

from PIL import Image, ImageDraw

CW = 760          # 每张缩略图宽
PER = 4           # 每张验片放几张源片（2x2）


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    if not os.path.isdir(src):
        raise SystemExit('素材目录不存在：' + src)
    files = sorted(glob.glob(os.path.join(src, '*.png')) + glob.glob(os.path.join(src, '*.jpg')))
    if not files:
        raise SystemExit('目录里没有 png/jpg：' + src)

    for s in range(0, len(files), PER):
        tiles = []
        for f in files[s:s + PER]:
            n = os.path.basename(f).rsplit('.', 1)[0].split('_')[-1]
            im = Image.open(f).convert('RGB')
            t = im.resize((CW, int(im.height * CW / im.width)), Image.LANCZOS)
            d = ImageDraw.Draw(t)
            th = t.height
            for k in range(1, 20):                    # 5% 网格，10% 用亮色
                x, y = CW * k / 20, th * k / 20
                col = (255, 170, 60) if k % 2 == 0 else (70, 110, 150)
                d.line([(x, 0), (x, th)], fill=col, width=1)
                d.line([(0, y), (CW, y)], fill=col, width=1)
            for k in range(1, 10):                    # 10% 标注
                d.text((CW * k / 10 + 2, 2), '%d0%%' % k, fill=(255, 210, 120))
                d.text((2, th * k / 10 + 2), '%d0%%' % k, fill=(150, 220, 255))
            d.rectangle([0, 0, CW - 1, 22], fill=(0, 0, 0))
            d.text((6, 5), n, fill=(255, 120, 120))
            tiles.append(t)

        cols = 2
        rows = (len(tiles) + 1) // 2
        TH = max(t.height for t in tiles)
        sheet = Image.new('RGB', (cols * CW, rows * TH), (18, 20, 26))
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % cols) * CW, (i // cols) * TH))
        p = os.path.join(out, '网格验片_%d.png' % (s // PER + 1))
        sheet.save(p)
        print(p, sheet.size)

    print('\n读框提示：把元素的四个边界写成比例 (x0,y0,x1,y1)，填进 extract_3d.py 的 OVERRIDES。')
    print('收紧原则 —— 标题文字必须排除；标注气泡若紧贴元素，先试着收到刚好不碰元素为止。')


if __name__ == '__main__':
    main()