#  NoteTori-RAG: 基于 Flask 的私有笔记知识库系统

> **项目简介**：这是我（一名大二学生）开发的第一个 RAG（检索增强生成）应用。这是一个基于 Python Flask 框架的私有笔记知识库系统，旨在结合 AI 技术，让个人笔记不仅能“存”，还能通过 AI 聊天进行“问”和“用”。

##  功能亮点

- ** 用户认证系统**：支持用户注册与登录，保障笔记数据的私密性。
- ** 笔记管理**：实现笔记的创建、编辑、查看与列表展示。
- **AI 智能问答**：内置 RAG 聊天页面，支持基于私有笔记内容的 AI 对话检索。
- **模板继承**：使用 Jinja2 模板继承机制（Base Template），保持页面导航栏与布局的统一。

## 🛠️ 技术栈

- **后端框架**：Python Flask
- **前端技术**：HTML5, CSS3, Jinja2 Templates
- **核心特性**：RAG (Retrieval-Augmented Generation) 检索增强生成

## 项目结构

```text
NoteTori-RAG/
├── app.py                  # 核心应用文件（包含所有路由与业务逻辑）
├── templates/              # HTML 页面模板目录
│   ├── base.html           # 公共基础模板（包含导航栏等公共元素）
│   ├── login.html          # 用户登录页面
│   ├── register.html       # 用户注册页面
│   ├── index.html          # 笔记列表主页
│   ├── create_note.html    # 创建笔记页面
│   ├── edit_note.html      # 编辑笔记页面
│   └── chat.html           # AI 聊天问答页面 (RAG核心交互)
└── README.md               # 项目说明文档
