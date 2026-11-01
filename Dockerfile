# 돌잡이 앱 서버 (Hugging Face Spaces, Docker). 묶음은 scripts/deploy_hf.sh 가 build/space/ 에 만든다.
# 키는 이미지에 넣지 않는다: Space Settings → Secrets (LLM_BASE_URL, LLM_API_KEY, … ) 가 환경 변수로 들어온다.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CACHE_MODE=nostore PORT=7860
WORKDIR /app

COPY requirements.lock pyproject.toml ./
COPY src ./src
RUN pip install -r requirements.lock && pip install -e . --no-deps

COPY app ./app
COPY web ./web
COPY config.yaml ./
COPY data ./data
COPY index ./index

# Spaces 는 사용자 1000으로 실행한다
RUN useradd -m -u 1000 user && chown -R user /app
USER user

EXPOSE 7860
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "7860"]
