# icon-spotlight-video

**深蓝聚光式 3D 图标视频** —— 一束光打在 3D 主体上，配数据卡片或逐条字幕的竖屏信息图动效版式。

![元素库总览](assets/elements/_overview.png)

手上一批 AI 生成的 3D 概念图（一张幻灯片 = 一个 3D 元素 + 若干标注），
抠出元素本体、换上视频底色，配一套「聚光 + 卡片」版式，直接渲成竖屏成片。
**不需要建模、不需要 three.js、不需要 WebGL。**

配套的逐帧渲染链路（Chrome headless 截图 + ffmpeg 编码）复用
[`html-timeline-video`](https://github.com/lyc4614/html-timeline-video)，本仓库只管这套版式独有的决策与坑。

## 什么时候用

| 场景 | 走哪条 |
|---|---|
| 手上有一批 3D 图标素材，想做成讲解 / 盘点类竖屏视频 | ✅ 本仓库 |
| 只有数据、没有主体形象 | 用 `html-timeline-video` 的卡片信息图方案，更省事 |
| 需要精确图表（折线 / 柱状 / 对比条） | 同上，聚光版式塞不下图表 |
| 主体需要连续运动（人物走路、流程推进） | 静态 PNG 撑不住，用纯 CSS 3D（`html-timeline-video` 的等距场景章节） |

## 快速开始

```bash
# ① 建工程
mkdir myproj && cd myproj && mkdir assets fonts
cp <REPO>/assets/template.html index.html
cp <REPO>/assets/fonts/*.woff2 fonts/            # 四个文件必须一起拷，见 fonts/README.md
cp <REPO>/assets/elements/elem_*.png assets/     # 15 个现成元素，也可只挑你需要的

# ② 改 index.html 里的 SHOTS（分镜表），src 改成 assets/xxx.png

# ③ 量化自检（强烈建议，别跳过 —— 卡片糊进背景肉眼看不出来）
cp <REPO>/assets/probe_rects.cjs <REPO>/assets/check_contrast.py .
node probe_rects.cjs 11.4                       # DOM 取矩形 → rects.json（同时查素材是否缺失）
python check_contrast.py 静帧.png rects.json    # 算明度分离度，不达标退出码 1

# ④ 渲染
VIDEO_ROOT=$PWD VIDEO_W=1080 VIDEO_H=1920 VIDEO_FPS=30 VIDEO_CRF=19 \
  node <html-timeline-video>/assets/render.cjs
```

## 三种呈现形态

| 形态 | 用在哪 | 结构 |
|---|---|---|
| `hero` | 开场封面 | 大标题 + 元素 + 底部黑条字幕 |
| `bullets` | 没有可对比数字时 | 元素 + 下方逐条说明（圆形序号） |
| `cards` | 有可量化数字时 | 元素 + 底部数据卡（可加标签胶囊） |

## 这套方法论最值钱的几条

**1. 裁框只能人工读，自动定位全败。**
源素材是「幻灯片 = 3D 图 + 中文标题」。标题文字的边缘梯度**比 3D 元素更强**
（文字是硬边，3D 渲染是软光），所以任何「找最亮 / 最大连通域 / 投影主峰」的判据
都会先选中标题。实测四种判据（二次曲面拟合、IRLS 重拟合、亮度投影、连通域）全部失败。
正解：`grid_sheet.py` 出 5% 坐标网格验片，人工读框填进 `OVERRIDES`。

**2. 底色替换用常量偏移，绝不做曲面拟合。**
素材底色是「上亮下暗 + 顶部集中辉光」的非多项式形状：
二次曲面拟合会让中下部被抬高、底边过度扣除（实测 22~46% 像素被截断）；
IRLS 迭代重拟合会**下行失控** —— 拟合面越降越低，最后塌到 ≈0，残差图全亮、判据全废。
`out = img − 外圈环带均值 + 目标底色`，有界、不失控。

**3. 暗角必须分两层。**
重暗角（`.vig`）在内容**之下**压背景，轻收边（`.vig2`）在内容**之上**。
整层盖在内容上时，卡片对背景的明度差会从 **+0.198 掉到 +0.062**（判据要 >0.15）——
卡片直接糊进背景，**肉眼完全看不出来**。

**4. 量化必须按元素类型分判据。**
实体卡片量全矩形；带羽化透明边的 3D 元素**只取中心约 52% 的「芯」**；
黑底字幕条不判定（靠描边和文字对比立住）。
不分类会产生假阴性 —— 实测把 hero 量成 +0.070 误判为「未达标」，
它其实立得住（+0.197），是四周半透明边把均值拖低了。

**5. 写检查工具必须双向验证，且反例要复原真实故障。**
正例通过不算数。第一次造反例只挪了「轻收边层」（影响太小查不出来），
复原真正的故障（重暗角压 0.86 盖在内容上）才抓出 +0.062。

**6. 素材路径写错时 `<img>` 不报错**，只是变成 0×0 空框 ——
所有量化照样「全部达标」，成片里却是一块空白。`probe_rects.cjs` 加了资源自检拦这个。

**7. 四个字体文件必须一起拷。**
模板声明了 4 个 `@font-face`，少拷一个，渲染链路会直接中止并报「字体未就绪」。
这是刻意的硬断言：`await document.fonts.ready` 在无 pending 请求时会立刻 resolve，
只等它会拿到「以为加载好了、其实还是回退字体」的页面，
而且这种错误 **PSNR 查不出来**（成片和帧序列错得一模一样）。

## 性能

1080×1920 实测 **0.53 s/帧**（普通信息图动效是 0.17，慢 3 倍，
成因是 `mix-blend-mode:screen` + 大 blur + 大图解码）。
3 分钟的片子 ≈ 45 分钟渲染。元素已压到 1200px 宽，再压收益很小。

## 目录结构

```
SKILL.md              完整方法论（每一步的坑、自查清单）
assets/
  template.html       竖屏模板，4 镜头示例覆盖三种形态
  elements/           15 个抠好的元素（底色已换成 #0F1A28）+ 总览图
  fonts/              Noto Sans/Serif SC 各两个字重（OFL 1.1，不随 MIT）
  grid_sheet.py       出 5% 坐标网格验片（人工读框用）
  extract_3d.py       按人工框抠图 + 底色常量偏移替换
  probe_rects.cjs     DOM 取矩形 → rects.json + 资源自检
  check_contrast.py   算明度分离度，不达标退出码 1
```

## 许可

代码 MIT。字体为 Noto Sans SC / Noto Serif SC（SIL OFL 1.1，见 `assets/fonts/README.md`）。
`assets/elements/` 里的元素由 AI 生成图抠出，可自由使用。