# commit-poem

GitHub 커밋 메시지를 읽어 매일 다른 시인 스타일로 영어/한글 시 2편을 생성하고, Slack에 전송하는 CLI 도구.

## 특징

- 영어 시 + 한글(영한 혼용) 시 동시 생성
- 매일 다른 시인 스타일 (한국 시인 100명 + 외국 시인 100명)
- OpenAI / Anthropic 백엔드 지원
- `.env` 자동 로드
- 스케줄 모드 (`--schedule`) 또는 cron 연동

## 설치

### 방법 1: pip로 설치 (권장)

```bash
pip install git+https://github.com/qo-kr/commit-poem.git
```

설치 후 바로 `commitpoem` 명령어를 사용할 수 있습니다.

### 방법 2: pipx로 설치 (격리 환경)

```bash
pipx install git+https://github.com/qo-kr/commit-poem.git
```

시스템 파이썬 환경을 오염시키지 않고 독립된 환경에 설치됩니다.

### 방법 3: 소스에서 개발용 설치

```bash
git clone https://github.com/qo-kr/commit-poem.git
cd commit-poem
uv venv
uv pip install -e '.[dev]'
```

## 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 값을 채워 넣으세요
```

필요한 환경변수:

| 변수 | 설명 | 필수 |
|------|------|------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | O |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL | O |
| `LLM_API_KEY` | OpenAI 또는 Anthropic API 키 | O |
| `LLM_BACKEND` | `openai` 또는 `anthropic` (기본: `anthropic`) | X |
| `LLM_MODEL` | 모델명 (기본: 백엔드별 자동 선택) | X |

자세한 발급 방법은 `.env.example` 파일 참고.

## 실행

```bash
# 한 번 실행
commitpoem \
  --repo owner/repo \
  --since 2026-03-23T00:00:00Z \
  --until 2026-03-24T00:00:00Z

# 30분마다 반복 실행
commitpoem \
  --repo owner/repo \
  --since 2026-03-23T00:00:00Z \
  --until 2026-03-24T00:00:00Z \
  --schedule 30m
```

## Cron 등록 (매일 자동 실행)

래퍼 스크립트 `run-daily.sh`를 cron에 등록하면 매일 자동으로 실행됩니다.

```bash
# crontab 편집
crontab -e

# 아래 줄 추가 (매일 오전 9시)
0 9 * * * /path/to/commit-poem/run-daily.sh >> /tmp/commitpoem.log 2>&1
```

로그 확인: `tail -f /tmp/commitpoem.log`

## 테스트

```bash
pytest -q
ruff check .
```
