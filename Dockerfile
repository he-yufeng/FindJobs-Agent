# 后端镜像：打包后的 findjobs 包 + gunicorn。
# 前端不在镜像里，api_server 只提供 /api（CORS 已开），FrontEnd 单独部署。
FROM python:3.12-slim

WORKDIR /app

# 打包元数据和源码
COPY pyproject.toml README.md ./
COPY findjobs/ findjobs/

# 运行期数据：标签库、示例岗位、LLM 默认配置
COPY data/ data/
COPY config/ config/

RUN pip install --no-cache-dir .

# 运行期目录：上传的简历、面试报告
RUN mkdir -p uploads report

ENV PORT=7860
ENV PYTHONUNBUFFERED=1
EXPOSE 7860

# LLM key 走环境变量注入（OPENROUTER_API_KEY / OPENAI_API_KEY），不要打进镜像
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 findjobs.api_server:app"]
