# 招聘信息自动化获取推送助手

> 以 `HTTP/SSR 主抓` 为核心链路，抓取 `智联招聘 + 牛客网` 的实习类数据分析岗位家族，覆盖 `杭州、上海、南京` 3 个城市。智联招聘负责主抓，牛客网仅在最终结果不足时补量；清洗后按排序和配额限制截断到约 `450` 条，再执行飞书全量覆盖写入。支持 GitHub Actions 每日定时运行，低质量结果会直接失败并保留飞书旧数据。

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
│   ├── base.py               # HTTP Session、请求头与重试
│   ├── nowcoder.py           # 牛客补量抓取（查询页 + 详情页）
│   └── zhilian.py            # 智联主抓（SSR 初始态解析）
├── cleaner.py                # 去重、排序、配额限制、质量校验
├── config.py                 # 运行时配置（城市优先级、关键词、配额、飞书环境变量）
├── feishu.py                 # 飞书多维表格 API 集成
├── main.py                   # 主入口
├── utils.py                  # 工具函数（静态 UA、时间戳等）
├── requirements.txt          # Python 依赖
└── README.md                 # 本文件
```

---

## 🏙️ 抓取城市范围

| 省份/直辖市 | 城市 |
|-----------|------|
| 浙江省 | 杭州 |
| 直辖市 | 上海 |
| 江苏省 | 南京 |

**总计 3 个城市**，优先级按 `杭州 > 上海 > 南京` 控制。

## 📋 职位类型筛选

| 平台 | 角色家族 | 抓取策略 |
|------|----------|----------|
| 智联招聘 | 数据分析、商业分析、经营分析、数据运营、数据产品分析、用户研究 | 按城市优先级和关键词分页抓取，杭州页数最高 |
| 牛客网 | 同上 | 仅在智联清洗后结果不足目标值时补量，按查询词抓详情页 |

目标是将**最终写入飞书的记录数**稳定控制在约 **450 条**，而不是单纯追求原始抓取量。

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

> 当前版本使用 HTTP/SSR 抓取链路，不需要安装 Playwright 浏览器。

### 3. 配置飞书 API（见下文详细步骤）

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

### 4. 运行

```bash
# 按“智联主抓 -> 必要时牛客补量 -> 质量校验 -> 飞书同步”运行
python main.py

# 仅抓取数据不写入飞书（调试用）
python main.py --dry-run
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
| 工作地点 | 文本 | 具体城市名称：杭州 / 南京 / 上海 |
| 岗位描述 | 文本 | 详情页抓取的 JD 全文 |
| 岗位类型 | 文本 | 实习 |
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
- 单次运行限制: `30 分钟`
- 产物: 始终上传 `output/*.csv`，便于排查低质量失败

---

## 🛡️ 抓取与控量策略

| 策略 | 实现方式 |
|-----|---------|
| HTTP/SSR 主抓 | 智联招聘直接解析页面内嵌初始态，避免浏览器渲染开销 |
| 牛客补量 | 仅在清洗后结果不足目标值时触发，降低总耗时 |
| 城市优先级 | 杭州相关关键词和页数优先，上海次之，南京再次之 |
| 请求控制 | 统一 Session、浏览器样式请求头、失败重试 |
| 结果控量 | 去重、排序、公司软上限后截断到目标条数 |

---

## 📊 数据清洗规则

### 工作地点标准化
工作地点自动提取到**市级**名称：
- `上海·浦东新区` → `上海`
- `杭州市` → `杭州`
- `南京市江宁区` → `南京`
- `宁波-鄞州区` → `宁波`

### 技术工具提取
从 JD 中匹配: SQL, Python, Tableau, Excel, Power BI, Spark, Hive 等 40+ 关键词

### 业务关键词提取
从 JD 中匹配: 留存分析, 漏斗模型, 用户画像, A/B测试, 数据看板 等 30+ 关键词

---

## 📝 注意事项

1. **仅保留 2 个站点**: 当前正式链路只跑智联招聘和牛客网。
2. **仅保留 3 个城市**: 杭州、上海、南京，且排序向杭州倾斜。
3. **角色范围已扩展**: 不只抓“数据分析实习”，还覆盖商业分析、经营分析、数据运营、数据产品分析、用户研究等同族岗位。
4. **最终目标是写入数**: 通过清洗、去重和公司软上限后，尽量稳定写入约 450 条。
5. **质量门槛先于覆盖同步**: 若有效总量、智联占比或杭州占比不达标，流程会直接失败，不会清空并覆盖飞书旧数据。
6. **CSV 输出始终保留**: 每次运行都会在 `output/` 下生成原始与最终结果 CSV，供 GitHub Actions 回传排查。
7. **SIGTERM 信号处理**: GitHub Actions 取消时会优雅退出并保存已有输出。
8. **数据合规**: 请确保爬取行为符合各平台的使用条款和相关法律法规，仅供个人学习使用。

---

## 📄 License

本项目仅供学习交流使用。
