# 招聘信息自动化获取推送助手

> 自动爬取"牛客网、实习僧、智联招聘"三大平台的**数据分析**岗位，清洗后同步至**飞书多维表格（Bitable）**。支持 GitHub Actions 每日定时运行。

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
│   ├── nowcoder.py           # 牛客网爬虫（列表页 + 详情页 JD）
│   ├── shixiseng.py          # 实习僧爬虫（列表页 + 详情页 JD）
│   └── zhilian.py            # 智联招聘爬虫
├── cleaner.py                # 数据清洗模块（薪资标准化、关键词提取）
├── config.py                 # 配置模块（API 密钥、关键词、爬虫参数）
├── feishu.py                 # 飞书多维表格 API 集成
├── main.py                   # 主入口
├── utils.py                  # 工具函数（随机 UA、延迟、滚动模拟）
├── requirements.txt          # Python 依赖
└── README.md                 # 本文件
```

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

| 字段名称 | 字段类型 |
|---------|---------|
| 公司名称 | 文本 |
| 岗位名称 | 文本 |
| 薪资原始 | 文本 |
| 薪资下限 | 文本 |
| 薪资上限 | 文本 |
| 薪资单位 | 单选（月薪/日薪/年薪） |
| 工作地点 | 文本 |
| 岗位描述 | 文本 |
| 岗位类型 | 单选（全职/实习/兼职） |
| 来源平台 | 单选（牛客网/实习僧/智联招聘） |
| 技术工具 | 文本 |
| 业务关键词 | 文本 |

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

### 薪资标准化
- `15k-25k` → 薪资下限: `15000`, 薪资上限: `25000`, 薪资单位: `月薪`
- `8-12K/月` → 薪资下限: `8000`, 薪资上限: `12000`, 薪资单位: `月薪`
- `200-300元/天` → 薪资下限: `200`, 薪资上限: `300`, 薪资单位: `日薪`
- `面议` → 薪资下限: `""`, 薪资上限: `""`, 薪资单位: `""`

### 技术工具提取
从 JD 中匹配: SQL, Python, Tableau, Excel, Power BI, Spark, Hive 等 40+ 关键词

### 业务关键词提取
从 JD 中匹配: 留存分析, 漏斗模型, 用户画像, A/B测试, 数据看板 等 30+ 关键词

---

## 📝 注意事项

1. **选择器可能更新**: 招聘网站前端会不定期改版，如果爬虫失效，需要检查并更新 CSS 选择器。
2. **详情页访问耗时**: 牛客网和实习僧需要逐个访问详情页获取 JD，10 页数据量可能需要较长时间（~20 分钟）。
3. **飞书 API 限流**: 飞书开放平台有频率限制，批量写入时已做分批处理（每批 500 条）。
4. **数据合规**: 请确保爬取行为符合各平台的使用条款和相关法律法规，仅供个人学习使用。
5. **CSV 输出**: 每次运行产生的 CSV 文件保存在 `output/` 目录下，文件名包含时间戳。

---

## 📄 License

本项目仅供学习交流使用。
