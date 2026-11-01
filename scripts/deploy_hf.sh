#!/usr/bin/env bash
# 돌잡이를 Hugging Face Space 에 배포한다:  bash scripts/deploy_hf.sh
# 필요: .env 의 HF_TOKEN (write 토큰), HF_SPACE (예: 사용자이름/doljabi), index/ (PYTHONPATH=src python -m ragbot index)
# 앱이 쓰는 파일만 build/space/ 에 모아 그 폴더를 Space 저장소로 force push 한다. 토큰은 화면에 찍지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."

env_value() { { grep -E "^$1=" .env || true; } | head -1 | cut -d= -f2- | tr -d '\r'; }
HF_TOKEN="$(env_value HF_TOKEN)"
HF_SPACE="$(env_value HF_SPACE)"
DRY_RUN="${DRY_RUN:-}"   # DRY_RUN=1: build/space/ 만 만들고 push 하지 않음
if [ -z "$DRY_RUN" ] && { [ -z "$HF_TOKEN" ] || [ -z "$HF_SPACE" ]; }; then
  echo ".env 에 HF_TOKEN 과 HF_SPACE 를 넣어 주세요." >&2; exit 1
fi
[ -f index/manifest.json ] || { echo "index/ 가 없습니다: PYTHONPATH=src python -m ragbot index" >&2; exit 1; }

rm -rf build/space
mkdir -p build/space/data/programs build/space/app
cp -r Dockerfile requirements.lock pyproject.toml src web config.yaml index build/space/
cp app/api.py build/space/app/
cp -r data/parsed build/space/data/
cp data/programs/programs.json build/space/data/programs/
cp deploy/README.space.md build/space/README.md
find build/space -name "__pycache__" -type d -prune -exec rm -rf {} +

cd build/space
git init -q -b main
git lfs install --local >/dev/null
git lfs track "*.npy" >/dev/null
git add -A
git -c user.name=deploy -c user.email=deploy@doljabi.local commit -q -m "deploy $(date +%Y-%m-%d)"
if [ -n "$DRY_RUN" ]; then git ls-files | sed 's#/.*##' | sort | uniq -c; git lfs ls-files; exit 0; fi
git push -q --force "https://user:${HF_TOKEN}@huggingface.co/spaces/${HF_SPACE}" main 2>&1 | sed "s#${HF_TOKEN}#***#g"
echo "배포함: https://huggingface.co/spaces/${HF_SPACE}"
