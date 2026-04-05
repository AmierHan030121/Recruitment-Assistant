# 招聘信息自动化获取推送助手

> 自动爬取"牛客网、智联招聘"两大平台的**数据分析**岗位，按**浙江省（11市）、江苏省（南京/苏州/扬州）、广东省（广州/深圳/珠海）及北京、上海**共 18 个城市逐城市 × 逐职位类型抓取，工作地点统一归并到**省级**（浙江/江苏/广东/北京/上海），清洗后同步至**飞书多维表格（Bitable）**。北京和上海在智联招聘上最多抓取 5 页。支持 GitHub Actions 每日定时运行。

---

## 📁 项目结构

```
招聘信息自动化获取推送助手/
├── .github/
│   └── workflows/
│       └── main.yml          # GitHub Actions 定时任务配置
├── output/                   # CSV 输出目录
├── scrapers/
│   ├── __init__.py           # 爬虫包导出
│   ├── base.py               # 爬虫基类（浏览器管理、反爬策略）
│   ├── nowcoder.py           # 牛客网爬虫（城市级联筛选 × 职位类型标签 + 详情页 JD）
│   └── zhilian.py            # 智联招聘爬虫（城市 URL 参数 × 职位类型筛选 + 详情页 JD）
├── cleaner.py                # 数据清洗模块（城市标准化、关键词提取）
├── config.py                 # 配置模块（API 密钥、关键词、目标城市列表、职位类型）
├── feishu.py                 # 飞书多维表格 API 集成
├── main.py                   # 主入口
├── utils.py                  # 工具函数（随机 UA、延迟、滚动模拟）
├── requirements.txt          # Python 依赖
└── README.md                 # 本文件
```

---

## 🏙️ 抓取城市范围

| 省份/直辖市 | 城市 | 工作地点输出 |
|-----------|------|------------|
| 浙江省（11市）| 杭州、宁波、温州、嘉兴、湖州、绍兴、金华、衢州、舟山、台州、丽水 | 浙江 |
| 江苏省（3市）| 南京、苏州、扬州 | 江苏 |
| 广东省（3市）| 广州、深圳、珠海 | 广东 |
| 直辖市（2市）| 北京、上海 | 北京 / 上海 |

**总计 18 个城市**，工作地点统一归并到省级名称。

## 📋 职位类型筛选

| 平台 | 职位类型（逐个筛选） | 翻页策略 |
|------|---------------------|----------|
| 牛客网 | 实习、校招、社招 | 每城市仅第 1 页 |
| 智联招聘 | 全职、兼职/临时、实习、校园 | 北京/上海最多 5 页，其余城市第 1 页 |

- 牛客网: 18 城市 × 3 类型 × 1 页 = **54 次搜索**
- 智联招聘: 16 城市 × 4 类型 × 1 页 + 2 城市 × 4 类型 × 最多 5 页 = **最多 104 次搜索**
- 总计最多约 **158 次搜索**（加上详情页访问）

---

## 🚀 快速开始

### 1. 创建并激活 Conda 环境

```bash
conda create -n job_scraper python=3.10 -y
conda activate job_scraper
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 安装 Playwright 浏览器

```bash
playwright install chromium
```

### 4. 配置飞书 API（见下文详细步骤）

设置环境变量：

```bash
# Linux/Mac
export FEISHU_APP_ID="cli_xxxxxx"
export FEISHU_APP_SECRET="xxxxxx"
export FEISHU_APP_TOKEN="bascnxxxxxx"
export FEISHU_TABLE_ID="tblxxxxxx"

# Windows PowerShell
$env:FEISHU_APP_ID="cli_xxxxxx"
$env:FEISHU_APP_SECRET="xxxxxx"
$env:FEISHU_APP_TOKEN="bascnxxxxxx"
$env:FEISHU_TABLE_ID="tblxxxxxx"
```

### 5. 运行

```bash
# 运行所有平台爬虫并同步到飞书
python main.py

# 仅运行智联招聘
python main.py --platform zhilian

# 仅抓取数据不写入飞书（调试用）
python main.py --dry-run

# 指定多个平台
python main.py --platform nowcoder zhilian
```

---

## 🔑 飞书 API 权限配置（详细步骤）

### Step 1：创建飞书应用

1. 打开 [飞书开放平台](https://open.feishu.cn/app)，登录后点击 **创建企业自建应用**。
2. 填写应用名称（如"招聘数据助手"）和描述，完成创建。
3. 在应用详情页获取 **App ID** 和 **App Secret**。

### Step 2：配置应用权限

进入应用的 **权限管理** 页面，搜索并开通以下权限：

| 权限名称 | 权限标识 |
|---------|---------|
| 查看、评论、编辑和管理多维表格 | `bitable:app` |
| 读写多维表格记录 | `bitable:app:record` |

> 开通后需要管理员审批通过。

### Step 3：创建多维表格

1. 在飞书中新建一个 **多维表格**。
2. 创建以下字段：

| 字段名称 | 字段类型 | 备注 |
|---------|---------|------|
| 公司名称 | 文本 | — |
| 岗位名称 | 文本 | — |
| 薪资 | 文本 | 如 `15K-25K`，无则填 `面议` |
| 工作地点 | 文本 | 省级名称：浙江 / 江苏 / 广东 / 北京 / 上海 |
| 岗位描述 | 文本 | 详情页抓取的 JD 全文 |
| 岗位类型 | 文本 | 全职 / 兼职/临时 / 实习 / 校园（智联）；实习 / 校招 / 社招（牛客） |
| 来源平台 | 文本 | 牛客网 / 智联招聘 |
| 技术工具 | 文本 | 从 JD 提取的技术关键词，逗号分隔 |
| 业务关键词 | 文本 | 从 JD 提取的业务关键词，逗号分隔 |

### Step 4：获取 APP_TOKEN 和 TABLE_ID

1. 打开多维表格，查看浏览器地址栏：
   ```
   https://xxx.feishu.cn/base/bascnXXXXXXX?table=tblXXXXXXX&view=vewXXXXXXX
   ```
2. `bascnXXXXXXX` 即为 **APP_TOKEN**
3. `tblXXXXXXX` 即为 **TABLE_ID**

### Step 5：将应用添加为表格协作者

在多维表格的 **分享** 设置中，将你创建的飞书应用添加为 **可编辑** 的协作者。

---

## ⚙️ GitHub Actions 自动化部署

### Step 1：推送代码到 GitHub

```bash
git init
git add .
git commit -m "init: 招聘信息自动化系统"
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

### Step 2：配置 GitHub Secrets

进入 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**：

| Secret 名称 | 值 |
|-------------|---|
| `FEISHU_APP_ID` | 飞书应用的 App ID |
| `FEISHU_APP_SECRET` | 飞书应用的 App Secret |
| `FEISHU_APP_TOKEN` | 多维表格的 APP_TOKEN（`bascnXXX`）|
| `FEISHU_TABLE_ID` | 数据表的 TABLE_ID（`tblXXX`）|

### Step 3：验证

- 自动运行: 每天 **北京时间 08:00** 自动执行
- 手动运行: 进入 **Actions** 标签页 → 选择 workflow → 点击 **Run workflow**

---

## 🛡️ 反爬策略说明

| 策略 | 实现方式 |
|-----|---------|
| 随机 User-Agent | 每次请求使用 `fake-useragent` 生成随机 UA |
| 随机延迟 | 每次页面操作间隔 3~8 秒随机等待 |
| 模拟滚动 | 使用 Playwright 模拟鼠标滚轮，距离和间隔随机化 |
| 无头浏览器 | Playwright Chromium 无头模式 + 反检测脚本 |
| 反 webdriver 检测 | 注入 JS 覆盖 `navigator.webdriver` 属性 |

---

## 📊 数据清洗规则

### 工作地点标准化
工作地点先提取到市级，再归并到**省级**名称：
- `北京市朝阳区` → `北京` → `北京`
- `广东-广州-天河区` → `广州` → `广东`
- `上海·浦东新区` → `上海` → `上海`
- `杭州市` → `杭州` → `浙江`
- `南京市江宁区` → `南京` → `江苏`

### 技术工具提取
从 JD 中匹配: SQL, Python, Tableau, Excel, Power BI, Spark, Hive 等 40+ 关键词

### 业务关键词提取
从 JD 中匹配: 留存分析, 漏斗模型, 用户画像, A/B测试, 数据看板 等 30+ 关键词

---

## 📝 注意事项

1. **按城市 × 职位类型抓取**: 牛客网通过页面城市级联筛选器逐城市勾选，同时分别选择"实习"/"校招"/"社招"标签页；智联招聘通过 URL `jl` 参数指定城市，再通过"职位类型"筛选下拉框分别选择"全职"/"兼职/临时"/"实习"/"校园"。
2. **18 个城市**: 浙江省 11 市 + 江苏省 3 市 + 广东省 3 市 + 北京 + 上海。工作地点归并到省级名称输出。
3. **智联多页抓取**: 北京和上海在智联招聘上最多抓取 5 页（无结果时自动停止），其余城市仅第 1 页。
4. **牛客登录弹窗**: 牛客网未登录状态下会弹出登录对话框阻止 UI 交互，爬虫通过 JS 隐藏弹窗解决。未登录时翻页内容重复，因此每城市仅抓取第 1 页。
5. **选择器可能更新**: 招聘网站前端会不定期改版，如果爬虫失效，需要检查并更新 CSS 选择器。
6. **飞书 API 限流**: 飞书开放平台有频率限制，批量写入时已做分批处理（每批 500 条）。
7. **数据合规**: 请确保爬取行为符合各平台的使用条款和相关法律法规，仅供个人学习使用。
8. **CSV 输出**: 每次运行产生的 CSV 文件保存在 `output/` 目录下，文件名包含时间戳。

---

## 📄 License

本项目仅供学习交流使用。
