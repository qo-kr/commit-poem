# commitpoem — 깃시인 유나

매일 한 번, qo-kr GitHub organization의 모든 repo에서 당일 커밋을 수집하고,
커밋 메시지와 변경 내용을 바탕으로 LLM이 시(詩)를 써서 Slack 채널에 발송하는 독립 서비스.

## 기능 요구사항

1. **GitHub 커밋 수집**: qo-kr org의 모든 repo에서 최근 24시간 커밋을 GitHub API로 수집
2. **시 생성**: 수집한 커밋 데이터를 LLM에 보내 한국어 또는 영어 시 1편 생성
3. **Slack 발송**: 생성된 시를 Slack incoming webhook으로 지정 채널에 포스팅
4. **스케줄링**: cron 또는 systemd timer로 매일 1회 실행 (예: 오전 9시)
5. **CLI**: `commitpoem run` (즉시 실행), `commitpoem preview` (Slack 미발송 미리보기)

## 비기능 요구사항

- Python 3.11+, Click CLI
- GitHub token은 환경변수 `GITHUB_TOKEN`으로 전달
- Slack webhook URL은 환경변수 `SLACK_WEBHOOK_URL`로 전달
- LLM 백엔드: OpenAI API (기본), 설정으로 변경 가능
- 커밋이 0건이면 "오늘은 조용한 날" 류의 시를 생성
