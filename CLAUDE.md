# CLAUDE.md — mpk-deck

> **역할 분담**: 이 파일은 **규칙과 설계 원칙**만 담는다 (상한 5KB).
> 아키텍처·기술 스택·하드웨어 MIDI 매핑·현재 진행 상태는 **`CONTEXT.md`가
> 정본**이다 — 코드 작업 전에 반드시 그쪽을 읽을 것. 워크스페이스 공통 규칙은
> `C:\DC\DD\CLAUDE.md`, 현황은 `C:\DC\DD\ROADMAP.md`, 결정 이력은
> `C:\DC\DD\docs\decisions\mpk-deck.md`.
> 여기에 상태·현황·아키텍처 서술을 추가하지 말 것. 두 사본은 반드시 갈라진다.

## 정체성

`mpk-deck`는 DD-PLAY-AI 시스템의 결정론적 실행 계층("hands")이다 —
Action Engine + PySide6 Personal Deck UI + AKAI MPK mini MK2 MIDI 제어.
AI 판단은 하지 않으며, 검증된 intent만 실행한다.

**단 하나의 의도적 예외:** `core/nl_action.py` — 자연어로 액션 바인딩을
제안받는 기능. Claude Haiku를 tool-forced 구조화 출력으로만 호출하고, 절대
자동 실행/저장하지 않는다 (제안된 값은 다이얼로그 필드만 채우고 사용자가 직접
Save를 눌러야 반영, 기존 `action_registry` 검증 경로를 그대로 통과).
2026-08-19 사용자가 명시적으로 승인한 범위 한정 예외 —
스펙: `docs/superpowers/specs/2026-08-19-nl-action-config-design.md`.

## 설계 원칙 (mpk-deck에 특히 적용)

- 이벤트 드리븐 MIDI만 사용 — 폴링 루프 금지 (`mido` 콜백 방식 유지).
- 액션은 항상 `config/actions.yaml` + Action Registry를 통해 구성 —
  하드코딩된 액션 금지. 새 액션 타입을 추가하면 `handlers.py`에 핸들러를
  추가하고 `ActionEngine`에 등록, `action_config_dialog.py`의
  `ACTION_CHOICES`/`ACTION_TYPE`/`PARAM_KEY`도 갱신.
- 데스크톱 UI는 항상 가볍게 — idle 상태 CPU/RAM 낮게, busy-wait 없음.
- Monitor Manager(Phase 2)는 미니 모니터 없이도 정상 동작해야 함 —
  아직 구매 전이므로 미니 모니터 존재를 전제하는 기능을 만들지 말 것.
- 하드웨어 종속 코드(win32gui, pycaw, mido/rtmidi)는 어댑터 함수 내부로
  격리하고 지연 import — 모듈 자체는 해당 하드웨어/OS 없이도 import 가능.

## 테스트 규칙

- `tests/`는 `src/mpk_deck/`와 1:1 구조를 유지한다
  (`core/action_engine.py` ↔ `tests/core/test_action_engine.py`).
- Qt 위젯(`ui/*_view.py`, `main_window.py`)과 실제 MIDI 포트 열기
  (`MPKController.start/stop`)는 pytest로 커버하지 않고 수동 검증한다.
  새 로직은 순수 함수로 뽑아낼 수 있으면 뽑아서 pytest로 커버할 것.
- **상수 재확인 테스트를 쓰지 않는다** — "내가 값을 의도적으로 바꿀 때만
  깨지는 테스트"는 버그를 잡지 못한다 (`~/.claude/CLAUDE.md` 코딩 스타일).
- 하드웨어 매핑은 pytest가 증명하지 못한다. **실기 O/X만 인정한다** —
  `C:\DC\DD\tasks\T-0002-mpk-deck-hardware-e2e.md`.

## 하드웨어 매핑을 만질 때

MIDI note/CC 값은 **`CONTEXT.md`의 "하드웨어 확정 매핑" 절이 유일한 정본**이다
(2026-09-02 실측 재캡처). 이 파일이나 오래된 plan 문서의 값을 믿지 말 것.
실측과 다르면 CONTEXT.md를 고치고, 코드를 실측에 맞춘다 — 반대가 아니다.
