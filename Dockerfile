FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .

ARG FQ_VERSION="fiinquantx"  # allow pinning e.g., fiinquantx==0.1.x
RUN pip install --no-cache-dir --extra-index-url https://fiinquant.github.io/fiinquantx/simple ${FQ_VERSION}
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python","-m","app.main"]
