FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .

ARG FQ_VERSION="fiinquantx"  # allow pinning e.g., fiinquantx==0.1.x
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --extra-index-url https://fiinquant.github.io/fiinquantx/simple ${FQ_VERSION}
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir tzdata

COPY . .
CMD ["python","-m","app.main"]
