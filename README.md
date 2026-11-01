# commit-poem

로컬 Git 저장소의 하루를 시와 그림으로 읽고, Slack에서 시인·화가를 한 명씩 알아가는 CLI 도구.

## 특징

- 한 작품의 영어 원문 + 한국어 번역, 두 판에 동일한 공통 이중언어 제목 표시
- 한국 시인 100명 + 외국 시인 100명, 역사적 세계 화가 100명의 매일 다른 조합
- 화가별 기법·색채·구도를 반영한 AI 시화 (그림 생성 실패 시 텍스트 게시)
- 커밋의 어떤 내용이 시의 이미지로 이어졌는지 설명하는 영한 Behind story
- 오늘의 시인·화가 소개, 대표작 및 위키/레퍼런스 링크
- 내용에 맞을 때만 출처가 있는 명언 추가 (배우·코미디언·정치인·철학가·역사가 등)
- 로컬 경로와 GitHub `origin`을 자동 연결; clone·worktree 사이의 동일 커밋 중복 제거
- 선택적으로 깨끗한 `main`만 fast-forward 업데이트
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
| `GITHUB_TOKEN` | GitHub API 수집용 Personal Access Token (로컬 모드에는 불필요) | API 모드만 |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL | O |
| `LLM_API_KEY` | OpenAI 또는 Anthropic API 키 | O |
| `LLM_BACKEND` | `openai` 또는 `anthropic` (기본: `anthropic`) | X |
| `LLM_MODEL` | 모델명 (기본: 백엔드별 자동 선택) | X |

자세한 발급 방법은 `.env.example` 파일 참고.

## 실행

```bash
# 로컬 저장소 중심 수집: 루트 자신과 바로 아래 clone/worktree를 읽음
# --org는 origin의 조직 필터; 여러 번 지정 가능
commitpoem \
  --local-root ~/genideas-labs --local-root ~/work-oq \
  --local-root /mnt/ssd4tb/genideas-secure-labs \
  --local-root /mnt/ssd4tb/k-gen-food \
  --org qo-kr --org genideas-secure-labs --org k-gen-food \
  --update-main \
  --since 2026-11-01T00:00:00+09:00 \
  --until 2026-11-01T23:59:59+09:00

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

로컬 모드에서는 로컬 브랜치, `origin` 원격 추적 브랜치와 worktree의 HEAD에 있는 커밋을
읽습니다. `--update-main`을 생략하면 네트워크 호출이나 브랜치 변경 없이 저장된 기록만 읽습니다.
외부 GitHub 전체 조직 조회는 `--local-root` 없이 `--org`를 지정하는 기존 API 모드로 사용할 수 있습니다.

`--update-main`은 **현재 브랜치가 main이고 추적/미추적 파일 변경이 없는 checkout**만 대상으로
원격 main을 fetch한 후 `merge --ff-only --no-autostash`를 실행합니다. 다른 브랜치나 detached
worktree, 수정 중인 checkout은 건너뜁니다. 이력이 갈라지거나 접근에 실패하면 경고 로그를
남기며 기존 로컬 기록으로 수집을 계속합니다. 자동 stash·rebase·충돌 해결은 하지 않습니다.
자동 동기화 중 merge hook은 실행하지 않습니다. 충돌을 임의로 해결하면 작업 의도를 훼손할 수 있어,
이력이 갈라진 저장소의 병합은 별도 검토 대상으로 남깁니다.
업데이트 동안 Git의 인덱스 잠금을 잡아 일반적인 checkout·switch·commit이 끼어들지 못하게 합니다.
이미 다른 Git 작업이 인덱스를 잠갔거나 병합·rebase·cherry-pick 등이 진행 중이면 건너뜁니다.

생성 결과는 JSON으로 검증하며, 형식이 잘못되면 한 번 수정을 요청합니다. 계속 잘못되면
게시하지 않고 실패 종료합니다. 해설은 개발자의 실제 심정을 단정하지 않는 창작 해석입니다.
소개와 대표작 링크는 모델이 만들지 않고 `commitpoem/data/`의 검토 가능한 목록에서 가져옵니다.
작품의 독립 문서가 없는 경우 해당 작품을 소개하는 인물 레퍼런스로 연결합니다.
시는 인물의 실제 작품으로 표시하지 않으며, 명언의 한국어 번역은 자체 번역임을 표시합니다.

## Cron 등록 (매일 자동 실행)

래퍼 스크립트 `run-daily.sh`는 위 네 로컬 루트에서 세 조직의 저장소를 수집합니다.
전날 00:00:00–23:59:59(Asia/Seoul)를 대상으로 하며, 깨끗한 main의 fast-forward를 켭니다.
시인·화가는 게시일의 서울 날짜 기준으로 선택하고, 각각의 목록을 모두 순회하기 전에는 반복하지 않습니다.
`COMMITPOEM_LOCAL_ROOTS`를 실행 환경에 colon(:)으로 구분해 설정하면 루트를 바꿀 수 있습니다.
모든 루트가 없으면 API 모드로 넘어가지 않고 실패합니다.

```bash
# crontab 편집
crontab -e

# 아래 줄 추가 (cron 서버의 현지 시각 매일 오전 9시; 현재 PC는 Asia/Seoul)
0 9 * * * /path/to/commit-poem/run-daily.sh >> /tmp/commitpoem.log 2>&1
```

로그 확인: `tail -f /tmp/commitpoem.log`

cron은 매번 checkout의 스크립트와 editable 설치를 읽으므로 이 PC에서는 별도 상주 데몬 재시작이
필요하지 않습니다. 원격 main 접근에는 각 저장소의 SSH 키 또는 Git credential helper가 사용됩니다.
GitHub API 토큰에 보이지 않는 조직도 로컬 clone과 Git 인증이 있으면 수집할 수 있습니다.
저장소별 수집 개수, 보이는 저장소가 없는 조직, 동기화를 건너뛴 이유는 로그에서 확인합니다.

## 테스트

```bash
pytest -q
ruff check .
```
