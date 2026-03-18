# First Prize RAG

## 项目简介

本项目用于实现“劳动合同风险识别与解释辅助系统”的核心工程链路，面向高校毕业生求职与签约场景，目标不是通用聊天机器人，而是围绕劳动合同审查建立完整流程：

- 合同解析与条款结构化
- 条款级风险识别
- 基于 LightRAG 的法律依据检索
- 基于大模型生成审查报告
- Markdown / PDF 报告导出

## 当前已实现能力

### 模块一：合同解析与条款结构化

当前支持以下输入：

- PDF 合同
- 单张图片合同（JPG / JPEG / PNG）
- 多张图片组成的合同页面序列
- 手机拍照合同图片（已预留图像预处理入口）

主链路：

`合同输入 -> 页面图像归一化 -> 百炼多模态识别 -> 文本清洗 -> 条款切分 -> 条款类型识别`

结构化输出字段保持稳定，正文条款包含：

- `clause_id`
- `section_title`
- `section`
- `title`
- `text`
- `clause_type`
- `part`

### 模块二：核心风险识别

当前采用规则优先的方式，对结构化条款做风险识别，支持输出：

- `risk_type`
- `risk_level_preliminary`
- `trigger_phrases`
- `key_risk_clauses`
- `attachment_risks`

### 检索与报告链路

当前已打通以下主链路：

`合同解析 -> 条款结构化 -> 模块二风险识别 -> 筛出 key_risk_clauses -> LightRAG 检索 labor_law / civil_code -> 大模型生成 Markdown 报告 -> PDF 导出`

其中：

- LightRAG 负责召回法律依据
- 大模型负责生成正式审查报告
- `main.py` 负责统一输出 Markdown / PDF

## 目录说明

- `app/`：主业务代码
  - `app/services/`：解析、切分、分类、风险识别、检索适配、报告编排
  - `app/config/`：风险规则与法律检索规则配置
- `ragmain/`：LightRAG 相关入口与查询脚本
- `rag_storage/`：已构建的法律知识库存储目录
  - `labor_law`
  - `civil_code`
- `dataset/`：法律文本原始材料
- `test/`：测试脚本
- `main.py`：统一输出入口（Markdown / PDF）
- `report_style.css`：正式审查报告 PDF 样式表

## 环境准备

推荐使用 Python 3.10+。

安装依赖：

```bash
pip install -r requirements.txt
```

### 环境变量

需要在项目根目录或 `ragmain/` 下准备 `.env` 文件，至少包含：

```env
DASHSCOPE_API_KEY="你的百炼 API Key"
```

如果使用多库检索，建议补充：

```env
LR_WORKING_DIRS=rag_storage/civil_code,rag_storage/labor_law
```

如需兼容旧的 LlamaParse 通道，可再配置：

```env
LLAMA_CLOUD_API_KEY="你的 LlamaParse API Key"
```

## 常用运行方式

### 1. 跑模块一解析链路

```bash
python test/test_bailian_parser.py
```

### 2. 跑 LightRAG 集成检索实验

```bash
python test/test_lightrag_integration.py
```

### 3. 跑法律依据检索实验

```bash
python test/test_lightrag_legal_review.py
```

### 4. 跑完整风险报告链路

```bash
python test/test_risk_report_pipeline.py
```

该命令会完成：

- 合同解析
- 风险识别
- 风险条款法律依据召回
- 生成 `report_context.json`
- 调用 `main.py` 生成 Markdown / PDF 报告

### 5. 直接根据现有 report_context 输出报告

```bash
python main.py --report-context data/output/report_context.json
```

## PDF 导出说明

项目当前优先使用：

- `pandoc`
- `wkhtmltopdf`
- `report_style.css`

生成正式审查报告版 PDF。

如果当前机器没有系统安装的 `wkhtmltopdf`，代码会优先尝试项目本地工具目录；若仍不可用，则回退到 PyMuPDF 导出。

## LightRAG 说明

- `ragmain/lightrag_embed.py`：知识库嵌入入口
- `ragmain/lightrag_query.py`：查询与报告生成入口
- `rag_storage/labor_law` / `rag_storage/civil_code`：当前已构建的法律知识库

当前版本不重建法律知识库，重点优化的是：

- 风险类型定向法律依据召回
- 检索结果去噪与排序
- 正式审查报告生成与导出

## 注意事项

- `.env` 不应提交到仓库
- `MDoutput/`、`PDFoutput/`、`data/output/` 属于运行产物，不建议提交
- `tools/` 下的本地便携工具属于环境辅助文件，不建议入库
- 本项目输出内容仅用于辅助审查，不构成正式法律意见
