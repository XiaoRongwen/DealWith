# DealWith - 视频/图片水印去除工具

一款基于深度学习的视频与图片水印自动检测与去除工具。支持自动识别水印位置（角落白色文字水印）和手动框选模式，采用 LaMa 深度修复模型实现高质量画面还原。

## 功能特性

- **自动水印检测**：基于多帧时序分析 + HSV 颜色特征，自动定位视频/图片角落的白色半透明文字水印
- **手动框选模式**：通过可视化画布手动框选水印区域，适用于非标准位置的水印
- **LaMa 深度修复**：使用 LaMa (Large Mask Inpainting) 模型进行高质量图像修复，支持 CPU/GPU
- **OpenCV 修复降级**：LaMa 不可用时自动降级为 OpenCV Telea/Navier-Stokes 算法
- **实时进度推送**：通过 WebSocket 实时展示处理进度、帧率和预计剩余时间
- **视频 + 图片支持**：支持 MP4/AVI/MKV 视频和 JPG/PNG/WEBP/BMP 图片
- **丰富的参数调节**：检测灵敏度、采样帧数、角落扫描范围、修复引擎、编码参数等均可自定义

## 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 运行环境 |
| FastAPI | Web 框架 & REST API |
| Uvicorn | ASGI 服务器 |
| OpenCV | 图像处理、视频解码编码 |
| NumPy | 数值计算 |
| simple-lama-inpainting | LaMa 深度修复模型 |
| Pillow | 图像 I/O |
| imageio-ffmpeg | FFmpeg 视频编解码 |
| WebSocket | 实时进度推送 |

### 前端

| 技术 | 用途 |
|------|------|
| Vue 3 | UI 框架 (Composition API) |
| TypeScript | 类型安全 |
| Vue Router | 路由管理 |
| Vite | 构建工具 & 开发服务器 |
| Tailwind CSS 4 | 样式框架 |
| Axios | HTTP 请求 |
| Konva / vue-konva | Canvas 手动框选交互 |
| VueUse | 组合式工具函数 |

## 项目结构

```
├── start.bat                    # 一键启动脚本 (Windows)
├── backend/
│   ├── requirements.txt         # Python 依赖
│   └── app/
│       ├── main.py              # FastAPI 应用入口 (CORS、静态文件、路由注册)
│       ├── api/
│       │   ├── routes.py        # REST API 路由 (上传/处理/状态/下载/取消)
│       │   ├── websocket.py     # WebSocket 进度推送
│       │   └── task_store.py    # 任务状态存储
│       ├── models/
│       │   └── schemas.py       # Pydantic 数据模型
│       └── pipeline/
│           ├── pipeline.py      # 处理主流水线 (解码→检测→修复→编码)
│           ├── decoder.py       # 视频解码器
│           ├── encoder.py       # 视频编码器
│           ├── detector.py      # 水印检测模块 (时序分析 + 角落扫描)
│           └── inpainter.py     # 图像修复引擎 (LaMa / OpenCV)
├── frontend/
│   ├── package.json             # Node.js 依赖
│   ├── vite.config.ts           # Vite 配置 (代理、测试)
│   ├── tailwind.config.js       # Tailwind 配置
│   ├── index.html               # HTML 入口
│   └── src/
│       ├── main.ts              # Vue 应用入口
│       ├── App.vue              # 根组件
│       ├── router/index.ts      # 路由配置
│       ├── types/index.ts       # TypeScript 类型定义
│       ├── api/client.ts        # API 请求封装
│       ├── views/
│       │   ├── UploadPage.vue   # 上传页面
│       │   ├── ProcessPage.vue  # 参数设置页面 (预览 + 手动框选/自动检测)
│       │   ├── ProgressPage.vue # 处理进度页面 (WebSocket 实时更新)
│       │   └── DownloadPage.vue # 下载结果页面
│       └── components/
│           ├── ToolLayout.vue   # 页面布局组件
│           ├── ManualMaskInput.vue  # 手动框选组件 (Konva Canvas)
│           └── InpaintConfig.vue    # 参数配置面板
└── tmp/                         # 临时文件目录 (任务数据、输入输出文件)
```

## 快速启动

### 环境要求

- Python 3.10+
- Node.js 18+
- FFmpeg（需在系统 PATH 中）

### 安装依赖

```bash
# 后端
pip install -r backend/requirements.txt

# 前端
cd frontend
npm install
```

### 一键启动 (Windows)

双击 `start.bat` 或在项目根目录执行：

```bat
start.bat
```

脚本会自动启动后端 (http://localhost:8000) 和前端 (http://localhost:5173)。

### 手动启动

```bash
# 启动后端 (项目根目录)
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# 启动前端 (frontend 目录)
cd frontend
npm run dev
```

启动后在浏览器打开 http://localhost:5173 即可使用。

## 使用流程

1. **上传**：拖拽或选择视频/图片文件上传（最大 2GB）
2. **参数设置**：选择自动检测或手动框选模式，调整修复参数
3. **处理**：实时查看处理进度、帧率和预计剩余时间
4. **下载**：处理完成后下载去水印结果文件（24小时内有效）

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload` | 上传视频/图片文件 |
| POST | `/process` | 启动处理任务 |
| GET | `/status/{task_id}` | 查询任务状态 |
| DELETE | `/task/{task_id}` | 取消处理任务 |
| GET | `/download/{task_id}` | 下载处理结果 |
| GET | `/preview/{task_id}` | 获取预览帧 |
| WS | `/ws/progress/{task_id}` | WebSocket 实时进度 |

## 配置说明

### 检测参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `detection_threshold` | 0.3 | 自动检测灵敏度 |
| `sample_frame_count` | 100 | 自动检测采样帧数 |
| `corner_scan_w` | 0.35 | 角落扫描宽度比例 (0.1~0.5) |
| `corner_scan_h` | 0.20 | 角落扫描高度比例 (0.1~0.4) |
| `color_sat_threshold` | 60 | 白色水印饱和度上限 (0~120) |
| `color_val_threshold` | 170 | 白色水印亮度下限 (100~255) |

### 修复参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `inpaint_engine` | `lama_cpu` | 修复引擎：`lama_cpu` / `lama_gpu` / `opencv` |
| `inpaint_algorithm` | `telea` | OpenCV 算法：`telea` / `navier_stokes` |
| `inpaint_radius` | 3 | OpenCV 修复半径 |
| `lama_context_pad` | 30 | LaMa 上下文 padding (px) |
| `static_background` | false | 静态背景模式：复用第一帧修复结果，更快 |

## License

MIT
