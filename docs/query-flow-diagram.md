# RAG 系统查询处理流程图

## 完整流程图

```mermaid
sequenceDiagram
    participant User as 👤 用户
    participant Frontend as 🌐 前端<br/>(script.js)
    participant API as 🔌 FastAPI<br/>(app.py)
    participant RAG as 🎯 RAG 系统<br/>(rag_system.py)
    participant Session as 💾 会话管理器<br/>(session_manager.py)
    participant AI as 🤖 AI 生成器<br/>(ai_generator.py)
    participant Claude as ☁️ Claude API<br/>(Anthropic)
    participant ToolMgr as 🔧 工具管理器<br/>(search_tools.py)
    participant Search as 🔍 搜索工具<br/>(CourseSearchTool)
    participant Vector as 📊 向量存储<br/>(vector_store.py)
    participant Chroma as 🗄️ ChromaDB

    User->>Frontend: 1. 输入问题<br/>"What is prompt caching?"
    Frontend->>Frontend: 2. 禁用输入框<br/>显示加载动画

    Frontend->>API: 3. POST /api/query<br/>{query, session_id}

    API->>Session: 4. 创建/获取会话
    Session-->>API: session_id

    API->>RAG: 5. query(query, session_id)

    RAG->>Session: 6. 获取对话历史
    Session-->>RAG: conversation_history

    RAG->>AI: 7. generate_response()<br/>+ tools + tool_manager

    Note over AI: 构建系统提示词<br/>+ 对话历史

    AI->>Claude: 8. 第一次 API 调用<br/>messages.create()<br/>+ tools定义

    Note over Claude: AI 决策：<br/>这是课程相关问题<br/>需要使用搜索工具

    Claude-->>AI: 9. stop_reason="tool_use"<br/>tool_name="search_course_content"<br/>input={query, course_name}

    Note over AI: 检测到工具调用<br/>开始处理工具执行

    AI->>ToolMgr: 10. execute_tool()<br/>("search_course_content", ...)

    ToolMgr->>Search: 11. execute()<br/>(query, course_name, lesson_number)

    Search->>Vector: 12. search()<br/>(query, course_name, lesson_number)

    Note over Vector: 步骤 1: 解析课程名称<br/>"Anthropic" → 完整标题

    Vector->>Chroma: 13a. 课程名称搜索<br/>course_catalog.query()
    Chroma-->>Vector: 匹配的课程标题

    Note over Vector: 步骤 2: 构建过滤器<br/>{course_title, lesson_number}

    Vector->>Chroma: 13b. 内容搜索<br/>course_content.query()<br/>+ 过滤器

    Note over Chroma: 1. 文本嵌入<br/>2. 向量相似度计算<br/>3. 过滤和排序<br/>4. 返回 Top-5

    Chroma-->>Vector: 14. 搜索结果<br/>{documents, metadata, distances}

    Vector-->>Search: 15. SearchResults 对象

    Note over Search: 格式化结果：<br/>[课程 - Lesson X]<br/>内容...<br/><br/>跟踪来源信息

    Search-->>ToolMgr: 16. 格式化的搜索结果<br/>+ 保存 last_sources

    ToolMgr-->>AI: 17. 工具执行结果

    Note over AI: 构建新的消息列表：<br/>1. 用户问题<br/>2. AI 的工具调用<br/>3. 工具结果

    AI->>Claude: 18. 第二次 API 调用<br/>messages.create()<br/>+ 工具结果

    Note over Claude: 基于搜索结果<br/>生成最终回答

    Claude-->>AI: 19. 最终回答文本

    AI-->>RAG: 20. response (回答文本)

    RAG->>ToolMgr: 21. get_last_sources()
    ToolMgr-->>RAG: sources 列表

    RAG->>ToolMgr: 22. reset_sources()

    RAG->>Session: 23. add_exchange()<br/>(query, response)

    RAG-->>API: 24. (answer, sources)

    API-->>Frontend: 25. JSON 响应<br/>{answer, sources, session_id}

    Frontend->>Frontend: 26. 移除加载动画<br/>渲染回答 (Markdown)<br/>显示来源列表

    Frontend->>User: 27. 显示结果 ✅
```

## 数据流详解

### 📤 请求数据结构

**前端 → 后端：**
```json
{
  "query": "What is prompt caching?",
  "session_id": "abc123"  // 可选，首次为 null
}
```

**工具调用参数（Claude → 搜索工具）：**
```json
{
  "name": "search_course_content",
  "input": {
    "query": "prompt caching",
    "course_name": "Anthropic",
    "lesson_number": null
  }
}
```

**向量搜索结果（ChromaDB → 向量存储）：**
```json
{
  "documents": [
    "Course ... Lesson 5 content: Prompt caching retains...",
    "Course ... Lesson 5 content: This can be a large cost..."
  ],
  "metadata": [
    {"course_title": "Building Towards...", "lesson_number": 5, "chunk_index": 42},
    {"course_title": "Building Towards...", "lesson_number": 5, "chunk_index": 43}
  ],
  "distances": [0.23, 0.31]
}
```

### 📥 响应数据结构

**后端 → 前端：**
```json
{
  "answer": "Prompt caching is a feature that retains some of the results...",
  "sources": [
    "Building Towards Computer Use with Anthropic - Lesson 5"
  ],
  "session_id": "abc123"
}
```

## 关键决策点

### 🤔 AI 决策：是否使用工具？

```mermaid
flowchart TD
    A[Claude 收到用户问题] --> B{问题类型判断}
    B -->|一般性知识问题| C[直接回答<br/>不使用工具]
    B -->|课程相关问题| D[使用 search_course_content 工具]

    C --> E[返回回答]

    D --> F[执行向量搜索]
    F --> G[获取相关内容]
    G --> H[Claude 基于搜索结果生成回答]
    H --> E

    style B fill:#ffe6e6
    style D fill:#e6f3ff
    style F fill:#e6ffe6
```

### 🔍 向量搜索流程

```mermaid
flowchart LR
    A[查询文本<br/>'prompt caching'] --> B[文本嵌入<br/>SentenceTransformer]
    B --> C[查询向量<br/>[0.12, -0.45, ...]]
    C --> D[相似度计算<br/>余弦相似度]
    D --> E[应用过滤器<br/>course_title, lesson_number]
    E --> F[排序<br/>按相似度]
    F --> G[返回 Top-5<br/>最相关文档块]

    style C fill:#ffe6e6
    style D fill:#e6f3ff
    style G fill:#e6ffe6
```

## 组件交互架构

```mermaid
graph TB
    subgraph "前端层"
        UI[Web 界面<br/>HTML/CSS/JS]
    end

    subgraph "API 层"
        API[FastAPI 应用<br/>app.py]
    end

    subgraph "业务逻辑层"
        RAG[RAG 系统<br/>rag_system.py]
        Session[会话管理器<br/>session_manager.py]
    end

    subgraph "AI 层"
        AI[AI 生成器<br/>ai_generator.py]
        Claude[Claude API<br/>Anthropic]
    end

    subgraph "工具层"
        ToolMgr[工具管理器<br/>ToolManager]
        Search[搜索工具<br/>CourseSearchTool]
    end

    subgraph "数据层"
        Vector[向量存储<br/>vector_store.py]
        Chroma[(ChromaDB<br/>向量数据库)]
        Docs[文档处理器<br/>document_processor.py]
    end

    UI <-->|HTTP JSON| API
    API --> RAG
    RAG --> Session
    RAG --> AI
    AI <-->|API 调用| Claude
    AI --> ToolMgr
    ToolMgr --> Search
    Search --> Vector
    Vector --> Chroma
    Docs --> Vector

    style UI fill:#e1f5ff
    style API fill:#fff3e0
    style RAG fill:#f3e5f5
    style AI fill:#e8f5e9
    style Vector fill:#fff9c4
    style Chroma fill:#ffebee
```

## 时序关系

### ⏱️ 两阶段 AI 调用

```mermaid
gantt
    title AI 生成器处理时序
    dateFormat X
    axisFormat %s

    section 第一阶段
    构建系统提示词 :a1, 0, 1
    第一次 Claude API 调用 :a2, 1, 3
    AI 决策（工具调用） :a3, 4, 1

    section 工具执行
    执行搜索工具 :b1, 5, 2
    向量搜索 :b2, 7, 3
    格式化结果 :b3, 10, 1

    section 第二阶段
    构建工具结果消息 :c1, 11, 1
    第二次 Claude API 调用 :c2, 12, 3
    生成最终回答 :c3, 15, 1
```

## 错误处理流程

```mermaid
flowchart TD
    A[开始查询] --> B{会话存在?}
    B -->|否| C[创建新会话]
    B -->|是| D[获取会话历史]
    C --> D

    D --> E[调用 AI 生成器]
    E --> F{AI 响应类型?}

    F -->|直接回答| G[返回回答]
    F -->|工具调用| H[执行搜索工具]

    H --> I{搜索结果?}
    I -->|成功| J[格式化结果]
    I -->|课程未找到| K[返回错误信息<br/>'No course found']
    I -->|无相关内容| L[返回空结果信息<br/>'No relevant content']
    I -->|搜索错误| M[返回错误信息<br/>'Search error']

    J --> N[第二次 AI 调用]
    K --> N
    L --> N
    M --> N

    N --> G
    G --> O[更新会话历史]
    O --> P[返回前端]

    style K fill:#ffcccc
    style L fill:#ffffcc
    style M fill:#ffcccc
```

## 性能优化点

### 🚀 优化策略

1. **工具调用优化**
   - AI 自主决定是否搜索（避免不必要的向量搜索）
   - 每次查询最多一次搜索

2. **向量搜索优化**
   - 限制返回结果数量（Top-5）
   - 使用过滤器减少搜索空间
   - ChromaDB 持久化存储

3. **会话管理优化**
   - 限制历史记录长度（最多 2 轮）
   - 避免上下文过长导致的成本增加

4. **API 调用优化**
   - 预构建系统提示词（静态常量）
   - 预构建基础 API 参数
   - Temperature=0（确定性输出）

## 总结

这个流程图展示了一个完整的 RAG 系统如何：
- ✅ 接收用户查询
- ✅ 智能决策是否需要搜索
- ✅ 执行语义向量搜索
- ✅ 基于检索结果生成回答
- ✅ 跟踪来源信息
- ✅ 维护对话上下文

核心特点是**两阶段 AI 调用 + 工具调用模式**，让 AI 自主决定何时需要检索外部知识。