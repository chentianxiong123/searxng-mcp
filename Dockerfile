FROM python:3.13-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY server.py .

# 暴露端口
EXPOSE 3000

# 启动服务器
CMD ["python", "server.py", "--http"]
