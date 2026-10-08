// probe_rects.cjs —— 用 getBoundingClientRect 量出「卡片 / 元素 / 背景」的精确矩形，输出 rects.json
//
// 为什么必须有这个脚本：
//   量化「卡片 vs 背景的明度差」时，人眼估的坐标一定是错的（已被骗过两次）。
//   硬编码像素坐标换一张素材就废。这里改成 DOM 取值 —— 换素材不用改脚本。
//
// 用法（在工程目录里）：
//   VIDEO_W=1080 VIDEO_H=1920 node probe_rects.cjs
//
// 改 TARGETS 就能换要量的对象。selector 选不中会直接报错退出（不静默返回 0，
// 否则你会以为「测出来没对比度」，其实是选择器没匹配）。

const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const ROOT = process.env.VIDEO_ROOT || __dirname;
const W = +(process.env.VIDEO_W || 1080);
const H = +(process.env.VIDEO_H || 1920);
const TIME = +(process.argv[2] || 0); // 在第几秒取样

// 背景参照区：每个 key 对应「要对比的背景位置」。
// 原则 —— 取被测元素【正上方 60~160px 处】、同宽的横条，那里一定没有卡片。
// mode 决定 check_contrast.py 怎么判：
//   'card'    实体卡片 —— 整个矩形参与判定（判据 Δ>=0.15）
//   'element' 带羽化透明边的元素 —— 只取中心 52% 的「芯」参与判定，
//              否则四周半透明像素把均值拖低，明明立得住也报未达标
//   'ref'     仅报告，不判定（黑底字幕条这类靠描边和文字对比的元素，
//              本来就是暗色压暗色，对背景的明度差没有意义）
const TARGETS = [
  { key: 'card0', mode: 'card',    sel: '.shot[style*="opacity: 1"] .card' },
  { key: 'card1', mode: 'card',    sel: '.shot[style*="opacity: 1"] .card:nth-child(2)' },
  { key: 'bullets', mode: 'card',  sel: '.shot[style*="opacity: 1"] .bullets' },
  { key: 'hero', mode: 'element',  sel: '.shot[style*="opacity: 1"] .hero img' },
  { key: 'cap', mode: 'ref',       sel: '.shot[style*="opacity: 1"] .cap span' },
];

function findChrome() {
  const c = [
    process.env.CHROME_PATH,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium',
  ].filter(Boolean);
  for (const p of c) if (fs.existsSync(p)) return p;
  throw new Error('找不到 Chrome，请设 CHROME_PATH');
}

(async () => {
  const b = await puppeteer.launch({
    executablePath: findChrome(), headless: 'new',
    userDataDir: path.join(ROOT, '.chrome-profile'),
    args: ['--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
           '--disable-lcd-text', '--font-render-hinting=none',
           '--allow-file-access-from-files', '--disable-gpu', '--disable-dev-shm-usage'],
  });
  const page = await b.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  await page.goto('file:///' + path.join(ROOT, 'index.html').replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.waitForFunction('typeof window.__render === "function"');
  await page.evaluate((t) => window.__render(t), TIME);
  await new Promise(r => setTimeout(r, 250));

  // ⚠️ 资源自检：素材缺失时 <img> 会静默变成 0×0 空框（不报任何错），
  //    后面所有量化照样"通过"，成片里却是一块空白。先拦下来。
  const badImgs = await page.evaluate(() => {
    const out = [];
    for (const im of document.querySelectorAll('.hero img')) {
      const r = im.getBoundingClientRect();
      if (r.width < 40 || r.height < 40) out.push({ src: im.getAttribute('src'), w: Math.round(r.width), h: Math.round(r.height) });
    }
    return out;
  });
  if (badImgs.length) {
    console.log('ERROR 素材没加载上（<img> 是空的，成片会是一块空白）：');
    for (const b of badImgs) console.log('   ' + b.src + '  实测 ' + b.w + 'x' + b.h + 'px');
    console.log('检查：文件是否拷进工程、src 路径相对 index.html 是否正确、文件名大小写');
    await b.close();
    process.exit(4);
  }

  const out = await page.evaluate((targets) => {
    const vis = [...document.querySelectorAll('.shot')]
      .filter(s => getComputedStyle(s).visibility !== 'hidden' && +getComputedStyle(s).opacity > 0.5);
    if (!vis.length) return { error: '该时刻没有可见镜头' };
    const R = (el) => {
      const r = el.getBoundingClientRect();
      return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)];
    };
    const rows = [];
    for (const t of targets) {
      const n = vis[0].querySelector(t.sel);
      if (!n) { rows.push({ key: t.key, mode: t.mode, missing: true }); continue; }
      const [l, tp, r, bm] = R(n);
      // 背景参照：同宽、位于元素正上方 90px 处的一条横带
      const bh = Math.max(20, Math.min(70, Math.round((bm - tp) * 0.16)));
      const by = Math.max(0, tp - bh - 24);
      let core = [l, tp, r, bm];
      if (t.mode === 'element') {           // 只量中心 52%，避开羽化透明边
        const ix = (r - l) * 0.24, iy = (bm - tp) * 0.24;
        core = [Math.round(l + ix), Math.round(tp + iy), Math.round(r - ix), Math.round(bm - iy)];
      }
      rows.push({ key: t.key, mode: t.mode, rect: core, full: [l, tp, r, bm], bg: [l, by, r, by + bh] });
    }
    return { rows };
  }, TARGETS);

  if (out.error) { console.log('ERROR ' + out.error); process.exit(2); }
  const missing = out.rows.filter(r => r.missing).map(r => r.key);
  out.viewport = [W, H];
  out.time = TIME;
  fs.writeFileSync(path.join(ROOT, 'rects.json'), JSON.stringify(out, null, 1));
  console.log('rects.json 已写出  t=' + TIME + 's  画幅=' + W + 'x' + H);
  for (const r of out.rows) {
    if (r.missing) console.log('  [缺失] ' + r.key + '  ← 该镜头没有这个元素（正常）或类名写错');
    else console.log('  ' + r.key.padEnd(8) + '(' + r.mode + ') rect=' + JSON.stringify(r.rect) + '  bg=' + JSON.stringify(r.bg));
  }
  await b.close();
  if (out.rows.every(r => r.missing)) { console.log('所有选择器都未命中 —— 页面结构可能变了'); process.exit(3); }
})().catch(e => { console.log('ERROR ' + (e && e.stack || e)); process.exit(1); });