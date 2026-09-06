# AGENTS.md

이 리포(`mpk-deck`)의 에이전트 가이드는 같은 디렉터리의 **`CLAUDE.md`** 와
**`CONTEXT.md`** 에서 유지된다. 둘 다 특정 에이전트 전용이 아니라 **모든
에이전트**를 위한 것이다 — "Claude"라고 쓰인 곳은 너에게도 동일하게 적용된다.

- `CLAUDE.md` — 정체성, 설계 원칙, nl_action 예외, 포인터. 규칙만, 5KB 상한.
- `CONTEXT.md` — 실제 아키텍처(코드 기준), 확정된 하드웨어 MIDI 매핑, 현재
  진행 상태(A~F). **코드 작업 전 반드시 읽을 것.** 하드웨어 매핑은 자주
  바뀌므로 이 파일에도 CLAUDE.md 에도 값을 적지 말고 `CONTEXT.md` 의
  "하드웨어 확정 매핑" 절만 신뢰할 것(2026-09-02 실측 재캡처가 정본).

- 워크스페이스 공통: `C:\DC\DD\CLAUDE.md`, `C:\DC\DD\ROADMAP.md`,
  `C:\DC\DD\docs\decisions\mpk-deck.md`
- Codex 공용 규칙: `~/.codex/AGENTS.md` (자동 로드)

이 파일에 프로젝트 사실을 적지 말 것 — 포인터일 뿐이다.
