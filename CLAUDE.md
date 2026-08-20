# CLAUDE.md

`mpk-deck`는 DD-PLAY-AI 시스템의 결정론적 실행 계층("hands")이다 —
Action Engine + PySide6 Personal Deck UI + AKAI MPK mini MK2 MIDI 제어.
AI 판단은 하지 않으며, 검증된 intent만 실행한다 (워크스페이스 루트
`C:\DC\DD\CLAUDE.md` 참고, 여기서 반복하지 않음). **단 하나의 의도적 예외:**
`core/nl_action.py` — 자연어로 액션 바인딩을 제안받는 기능. Claude Haiku를
tool-forced 구조화 출력으로만 호출하고, 절대 자동 실행/저장하지 않음
(제안된 값은 다이얼로그 필드만 채우고 사용자가 직접 Save를 눌러야 반영됨,
기존 `action_registry` 검증 경로를 그대로 통과). 2026-08-19 사용자가 명시적으로
승인한 범위 한정 예외 — 스펙: `docs/superpowers/specs/2026-08-19-nl-action-config-design.md`.

## 실제 아키텍처 (코드 기준)

- `core/action_engine.py`의 `ActionEngine`이 유일한 실행 진입점.
  `register_trigger`/`register_continuous`로 액션 이름 -> 핸들러 함수를
  등록하고, `load_bindings()`로 `control -> Binding(action, params)` 맵을
  적재한다. MIDI 콜백과 UI 클릭 둘 다 `engine.trigger(control)` /
  `engine.set_continuous(control, value)`만 호출하고, 직접 실행하지 않는다.
- `core/action_registry.py`: `config/actions.yaml`을 로드/저장. 잘못된
  바인딩은 예외를 던지지 않고 로그 후 skip (`ActionConfigError`는 파일
  자체가 없을 때만).
- `core/handlers.py`: 실제 side-effect 핸들러 (`launch_program`,
  `open_url`, `focus_window`, `set_system_volume`). 트리거 핸들러는
  `(params: dict) -> None`, continuous 핸들러는
  `(params: dict, value: float) -> None` 시그니처를 따른다. Windows 전용
  의존성(`win32gui`, `pycaw`)은 함수 내부에서 지연 import — 모듈 로드
  자체는 해당 패키지 없이도 가능해야 한다.
- `core/program_finder.py`: 시작 메뉴 `.lnk` 스캔해서 설치된 프로그램
  목록 제공 (프로그램 런처 UI용).
- MIDI 흐름: `midi/mpk_controller.py`의 `MPKController`가 `mido`로 MPK
  mini MK2 포트를 열고 콜백 기반으로 리슨 (폴링 없음) -> 각 메시지를
  `midi/translator.py`의 `translate()`(순수 함수, MIDI note/CC ->
  `ControlEvent`)로 변환 -> `ActionEngine.trigger`/`set_continuous` 호출.
  팩토리 기본 매핑: 패드 note 36-43 -> `pad_1`..`pad_8`, 노브 CC 1-8 ->
  `knob_1`..`knob_8`.
- `config/actions.yaml`이 바인딩의 source of truth. 손으로 수정하거나
  `ui/action_config_dialog.py`의 GUI로 수정 — 둘 다 같은
  `load_bindings`/`save_bindings`를 거친다.
- UI: `ui/main_window.py`가 통합 지점. `Qt.FramelessWindowHint` +
  `WA_TranslucentBackground`로 타이틀바/닫기버튼 없는 위젯형 창 — 열기/닫기/
  모드전환/테마전환은 시스템 트레이 아이콘 컨텍스트 메뉴로만 (`Toggle
  Mini/Expanded`, `Light Mode`/`Dark Mode`, `Quit`). 창 이동은 배경(패드
  사이 여백)을 마우스로 드래그, 리사이즈는 우하단 `QSizeGrip`. Mini 모드는
  `MINI_ASPECT`(가로:세로 = `COLS`/`ROWS` = 2.0)로 리사이즈 시 비율 고정
  (`resizeEvent`에서 높이를 폭에 맞춰 재보정, `_resizing_guard`로 재귀
  방지).
- `ui/mini_view.py`: 8패드를 `ui/grid_layout.py`의 `compute_pad_rects()`
  (정사각형 셀 레터박스 배치, 순수 함수, pytest 커버)로 수동 배치. 패드는
  `PadButton`(QPushButton 상속) — 단일클릭은 디바운스(`QApplication.
  doubleClickInterval()`) 후 `activated` 시그널(실제 액션 트리거), 더블클릭은
  타이머를 취소하고 `configure_requested` 시그널(설정 다이얼로그 오픈)을
  쏜다. `MainWindow`가 `pad_activated -> engine.trigger()`,
  `pad_configure_requested -> ActionConfigDialog` 로 각각 연결.
- 테마: `set_dark(bool)`로 Light/Dark 전환. Light는 실제로 반투명(흰색
  글래스, 어두운 텍스트), Dark는 어두운 글래스 배경에 밝은 텍스트
  (`#f2f4f8`, 이전엔 `#d7dae0`라 잘 안 보였음 — 가독성 때문에 밝게 조정).
  `ExpandedView`는 이번 라운드에서 테마 손 안 댐(레이블 잘림만 수정),
  다음 UI 라운드 대상.
- `core/program_finder.py`: Start Menu(`%APPDATA%`/`%PROGRAMDATA%`)의
  `.lnk` 재귀 스캔 -> `win32com.client`(WScript.Shell)로 타겟 exe resolve.
  `list_installed_programs(search_dirs=, resolver=)` 둘 다 주입 가능 —
  `focus_window`의 `finder` 패턴과 동일한 테스트 스타일. `ActionConfigDialog`가
  `launch_program` 선택 시 이 목록을 검색 가능한 리스트로 보여줌 (경로
  직접 입력/Browse는 폴백으로 유지).
- `ui/action_config_dialog.py`: 다크 테마 통일, 왼쪽에 액션 종류를
  아이콘+라벨 리스트(`QListWidget`)로, 오른쪽은 액션별 파라미터 페이지
  (`QStackedWidget`) — launch_program은 설치 프로그램 검색 리스트,
  open_url/focus_window는 텍스트 입력, set_system_volume은 안내 문구만.
- `config.py`: `DEFAULT_ACTIONS_PATH`, 모드/테마 영속화
  (`load_last_mode`/`save_last_mode`, `load_last_theme`/`save_last_theme`,
  전부 `QSettings`, 테마 기본값은 `"dark"`).
- `core/nl_action.py`: `parse_nl_action(text, installed_programs, client=None)
  -> Binding | None`. Claude Haiku 4.5를 tool_choice로 강제해 구조화 출력만
  받음 — `launch_program`은 모델이 고른 프로그램 이름이 실제 설치 목록에
  정확히 일치할 때만 허용(없는 경로 지어내는 것 차단). `client` 주입 가능
  (`handlers.py`의 `finder`/`volume_setter` 패턴과 동일), 실패/모호하면
  항상 `None`. `ANTHROPIC_API_KEY`는 `.env`(gitignored)에서
  `python-dotenv`로 `__main__.py`가 앱 시작 시 로드 — 앱 내 키 입력 UI 없음.
  `action_config_dialog.py`가 이 함수 호출 결과로 기존 폼 필드만 채움,
  저장은 여전히 사용자가 Save를 눌러야 함.

## 기술 스택 / 실행

- Python >= 3.13, 패키지 매니저는 표준 `pip` (editable install:
  `pip install -e ".[dev]"`) — `uv.lock` 등 lock 파일 없음, uv 미사용.
- 런타임: PySide6, mido, PyYAML, (win32) pycaw, pywin32. 선택 익스트라
  `midi-hardware`(`python-rtmidi`)는 실제 MIDI 하드웨어 백엔드가 필요할
  때만.
- 테스트: `pytest` (`pyproject.toml`의 `testpaths = ["tests"]`). 그냥
  `pytest`로 전체 실행. `tests/`는 `src/mpk_deck/`와 1:1 구조 (예:
  `core/action_engine.py` <-> `tests/core/test_action_engine.py`). Qt
  위젯(`ui/*_view.py`, `main_window.py`)과 실제 MIDI 포트 열기
  (`MPKController.start/stop`)는 pytest로 커버하지 않고 수동 검증 —
  새 로직을 넣을 때 순수 함수로 뽑아낼 수 있으면 그렇게 하고 pytest로
  커버할 것.

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

## 현재 진행 상태

Phase 1 MVP + UI 리디자인 + 자연어 액션 설정까지 `main`에 구현/커밋/푸시
완료 (Action Engine/Registry, 핸들러, MIDI 번역기/컨트롤러, Mini/Expanded
UI, Action Config Dialog, `core/nl_action.py`). pytest 전체 통과.

미해결/미검증 항목:
- Windows 창 제어는 `focus_window`만 구현 — move/resize/always-on-top 없음.
- 반투명 프레임리스 최상위 창은 `QWidget.grab()`/`render()` 자동 캡처가
  안 됨(Qt 캡처 한계, 자식 위젯 단독 캡처는 정상 — 스타일 자체는 검증됨).
  실제 데스크톱 컴포지팅(DWM)에서 어떻게 보이는지는 `python -m mpk_deck`로
  직접 확인 필요 (사용자 몫, 아직 미확인).
- 자연어 액션 설정 기능은 실제 API 키로 실행 검증 안 됨 — `.env`에
  `ANTHROPIC_API_KEY` 넣고 `python -m mpk_deck`에서 다이얼로그 열어 확인 필요.
- `ExpandedView`는 이번 라운드 범위 밖 (레이블 잘림 수정만 완료, 테마/
  더블클릭 분리는 다음 라운드).

다음 라운드(아직 브레인스토밍 전, 코딩 시작하지 말 것): ExpandedView의
조이스틱을 마우스 드래그로 상하좌우 스크롤 액션에 매핑 + 물리 MPK의 실제
조이스틱/피치벤드 MIDI도 같이 연결, 그리고 사용자가 지정한 건반 N개로
패드 매핑 페이지를 전환하는 기능. 둘 다 새 서브시스템(스크롤 액션 타입,
바인딩에 "페이지" 개념 추가)이라 스펙부터 써야 함.

Phase 2(멀티 모니터, Monitor Manager, Workspace Profiles)는 3.5" 미니
모니터 구매 전까지 착수하지 말 것.

사전 설계 문서: `docs/superpowers/specs/2026-08-17-phase1-mvp-design.md`,
계획: `docs/superpowers/plans/2026-08-17-phase1-mvp.md`,
`docs/superpowers/specs/2026-08-19-nl-action-config-design.md` +
`docs/superpowers/plans/2026-08-19-nl-action-config.md`.
