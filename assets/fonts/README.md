# fonts/

本目录的字体文件**不随仓库的 MIT 许可**，各自遵循自己的许可：

| 文件 | 许可 | 来源 |
|---|---|---|
| `NotoSansSC-Black.woff2` | SIL Open Font License 1.1 | Google Fonts（Noto Sans SC） |
| `NotoSansSC-Bold.woff2` | SIL Open Font License 1.1 | Google Fonts（Noto Sans SC） |
| `NotoSerifSC-Black.woff2` | SIL Open Font License 1.1 | Google Fonts（Noto Serif SC） |
| `NotoSerifSC-Bold.woff2` | SIL Open Font License 1.1 | Google Fonts（Noto Serif SC） |

OFL 1.1 允许自由使用、修改、再分发，包括**商用**，但要求：

- 保留版权与许可声明；
- **不得单独售卖字体本身**；
- 保留字体文件的名称（Reserved Font Name 条款）。

## ⚠️ 四个文件必须一起拷

`template.html` 声明了 4 个 `@font-face`（Sans 900/700 + Serif 900/700）。
**少拷任何一个，渲染链路会直接中止**并报：

```
fonts: 3/4 loaded  未加载: NSerif/900
✗ 字体未就绪 —— 继续渲会得到回退字体的画面，已中止
```

这是刻意的硬断言：`await document.fonts.ready` 在无 pending 请求时会**立刻 resolve**，
只等它会拿到「以为加载好了、其实还是回退字体」的页面，
而且这种错误 **PSNR 查不出来**（成片和帧序列错得一模一样）。

如果你不想在自己的项目里再分发二进制字体文件，**可以删掉本目录**，
但要同步把 `template.html` 里 4 个 `@font-face` 与 `fonts/` 拷贝步骤一起去掉。