FROM python:3.10-slim

# 安装 Node.js (用于构建前端)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制 Python 依赖并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制前端代码并构建
COPY FrontEnd/package.json FrontEnd/package-lock.json* FrontEnd/
RUN cd FrontEnd && npm install

COPY FrontEnd/ FrontEnd/
RUN cd FrontEnd && npm run build

# 复制后端代码和数据文件
COPY *.py ./
COPY *.csv ./
COPY *.json ./
COPY llm_config.json ./

# 创建必要的目录
RUN mkdir -p uploads report

# 暴露端口
EXPOSE 7860

# 设置环境变量
ENV PORT=7860
ENV PYTHONUNBUFFERED=1

# 启动应用
CMD ["python", "app.py"]
