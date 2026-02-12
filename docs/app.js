// ============================
// 全局状态
// ============================

let mode = "pure";      // 默认 pure
let currentMonth = null;
let currentFile = null;
let allFiles = [];

const base = ".."; // docs 在仓库根目录下，所以回到上一层访问 sgf/

let player = null;

// ============================
// 工具：列目录（解析 GitHub Pages 目录索引）
// ============================

async function listLinks(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error("Fetch failed: " + url);
  const html = await r.text();
  const doc = new DOMParser().parseFromString(html, "text/html");
  return [...doc.querySelectorAll("a")]
    .map(a => a.getAttribute("href"))
    .filter(Boolean)
    .filter(h => h !== "../");
}

// ============================
// UI 状态
// ============================

function setMode(newMode) {
  mode = newMode;
  document.getElementById("modePill").textContent = "当前：" + mode;
  document.getElementById("toggleBtn").textContent =
    mode === "pure" ? "切换到 AI（绝艺变化）" : "切换到 pure（主线）";

  if (currentFile) {
    loadGame(currentFile);
  } else {
    refreshFiles();
  }
}

function setActiveMonth(m) {
  currentMonth = m;
  currentFile = null;

  [...document.querySelectorAll("#months a")].forEach(a => {
    a.classList.toggle("active", a.dataset.month === m);
  });

  refreshFiles();
}

function setActiveFile(name) {
  currentFile = name;
  [...document.querySelectorAll("#files a")].forEach(a => {
    a.classList.toggle("active", a.dataset.file === name);
  });
}

// ============================
// 加载月份列表
// ============================

async function loadMonths() {
  const monthsBox = document.getElementById("months");
  monthsBox.innerHTML = "加载中...";

  // 只从 pure 目录读取月份（因为 pure/ai 结构完全一致）
  const links = await listLinks(`${base}/sgf/pure/`);
  const months = links
    .filter(h => h.endsWith("/"))
    .map(h => h.replace("/", ""))
    .sort()
    .reverse();

  monthsBox.innerHTML = "";
  for (const m of months) {
    const a = document.createElement("a");
    a.href = "javascript:void(0)";
    a.dataset.month = m;
    a.textContent = m;
    a.onclick = () => setActiveMonth(m);
    monthsBox.appendChild(a);
  }

  document.getElementById("monthHint").textContent =
    `共 ${months.length} 个月（默认 pure，可切换 AI 绝艺变化）`;

  if (months.length) setActiveMonth(months[0]);
}

// ============================
// 加载文件列表
// ============================

async function refreshFiles() {
  if (!currentMonth) return;

  const filesBox = document.getElementById("files");
  filesBox.innerHTML = "加载中...";

  const url = `${base}/sgf/${mode}/${currentMonth}/`;
  let links = [];
  try {
    links = await listLinks(url);
  } catch (e) {
    filesBox.innerHTML = `无法读取目录：${url}`;
    return;
  }

  const files = links.filter(h => h.endsWith(".sgf"));
  allFiles = files;

  renderFiles(files);

  if (files.length) {
    loadGame(files[0]);
  }
}

function renderFiles(files) {
  const filesBox = document.getElementById("files");
  const q = document.getElementById("search").value.trim().toLowerCase();

  const filtered = files.filter(f => f.toLowerCase().includes(q));

  filesBox.innerHTML = "";
  if (!filtered.length) {
    filesBox.innerHTML = "<div style='color:#666;'>没有匹配的 SGF</div>";
    return;
  }

  for (const f of filtered) {
    const a = document.createElement("a");
    a.href = "javascript:void(0)";
    a.dataset.file = f;
    a.textContent = f;
    a.onclick = () => loadGame(f);
    filesBox.appendChild(a);
  }
}

// ============================
// 加载棋谱到棋盘（支持变化树）
// ============================

async function loadGame(filename) {
  if (!currentMonth) return;

  setActiveFile(filename);

  const url = `${base}/sgf/${mode}/${currentMonth}/${filename}`;

  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) {
    alert("无法加载棋谱：" + url);
    return;
  }

  const sgf = await r.text();

  const el = document.getElementById("player");
  el.innerHTML = "";

  player = new WGo.BasicPlayer(el, {
    sgf: sgf,
    enableWheel: true,
    enableKeys: true,
    showCoordinates: true,
    markLastMove: true,
    boardSize: "auto"
  });

  document.getElementById("gameTitle").textContent =
    `[${mode.toUpperCase()}] ${filename}`;
}

// ============================
// 事件绑定
// ============================

document.getElementById("toggleBtn").onclick = () => {
  setMode(mode === "pure" ? "ai" : "pure");
};

document.getElementById("search").addEventListener("input", () => {
  renderFiles(allFiles);
});

// ============================
// 启动
// ============================

loadMonths();
