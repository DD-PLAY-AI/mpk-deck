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
  Mini/Expanded`, `Light Mode`/`Dark Mode`, `Always on Top`, `Quit`).
  창 이동/리사이즈는 2026-08-23 두 번 재설계 끝에 순수 Qt 레벨 수동 처리로
  정착 — 처음 시도했던 Windows 네이티브 `WM_NCHITTEST` 가로채기는 실사용
  검증에서 테두리도 안 잡히고 커서도 이상하게 나와 실패(PySide6 버전별
  `nativeEvent` 메시지 마샬링/반환 시그니처가 라이브 확인 없인 검증 불가능한
  영역이라 판단, `superpowers:systematic-debugging`의 "3번 이상 고쳐도 안
  되면 아키텍처를 의심하라" 기준에 따라 전면 재설계). 현재 구조:
  - `ui/hit_test.py`의 `classify_hit()` — 좌표가 테두리(`ui/window_grip.py`의
    `BORDER=6`px) 안쪽이면 어느 변/코너인지, 그 외 영역은 실제 클릭 가능한
    위젯(패드 버튼 등) 위인지에 따라 win32 HT* 상수를 반환하는 순수 함수
    (더 이상 실제 `WM_NCHITTEST`에 넘기지 않음 — 그냥 잘 정의된 zone id로
    재사용). pytest 커버.
  - `ui/resize_geometry.py`의 `compute_resized_rect()` — 어느 변/코너를
    드래그 중인지 + 델타(dx, dy) + 잠글 비율(aspect)을 받아 새
    (x, y, w, h)를 계산하는 순수 함수. 드래그 반대쪽 변/코너를 앵커로
    고정하고, E/W/코너는 폭이 델타를 따라가고 높이가 유도되고, N/S는
    반대로 높이가 델타를 따라가고 폭이 유도됨. pytest 커버(줌/코너별
    앵커 이동 케이스 전부).
  - `ui/window_grip.py`의 `WindowGripMixin` — `MiniView`/`ExpandedView`
    양쪽에 믹스인. `setMouseTracking(True)`로 버튼 안 눌러도
    `mouseMoveEvent`가 계속 들어오게 해서, 호버 중엔 `classify_hit()`
    결과에 맞는 커서(`SizeHorCursor`/`SizeVerCursor`/`SizeFDiagCursor`/
    `SizeBDiagCursor`/`SizeAllCursor`)를 직접 `setCursor()`. 마우스
    누른 채 이동이면 `mousePressEvent`에서 잡아둔 zone에 따라
    `compute_resized_rect()`(리사이즈 zone) 또는 단순 오프셋
    이동(`HTCAPTION`)으로 `self.window()`의 geometry를 직접 갱신 — OS
    네이티브 API 전혀 안 씀, 전부 우리가 계산.
  - **커서가 패드 위까지 새던 버그**(`setCursor()`가 자기 커서 없는 자식
    위젯에 상속되는 Qt 기본 동작 때문)도 이 재설계에서 근본적으로 해결—
    `PadButton`과 `ExpandedView`의 모든 버튼/키(`QFrame`)에 생성 시점에
    `Qt.CursorShape.PointingHandCursor`를 명시적으로 지정해서 부모의
    동적 커서를 상속받지 않게 함.
  - 이전의 수동 `DraggableMixin`(`ui/window_drag.py`)과 `QSizeGrip`은 둘 다
    삭제 — 코너 grip 하나뿐이라 리사이즈 지점이 좁고, 종횡비 보정 후 위치가
    틀어져 화면 밖으로 나가는 버그가 있었음.
  - 테두리는 시각적으로도 보이게 — 단, 잡는 영역(`BORDER=6`px, 히트테스트용)과
    실제로 그리는 선 두께는 분리(`frontend-design` 스킬 리뷰 결과: 작은
    위젯에 6px 통 컬러 테두리는 무겁고 "얇은 테두리" 요청과도 안 맞음).
    `MiniView`/`ExpandedView` 각자 `BORDER_VISUAL=2`px로 액센트 컬러
    (`ACCENT_RGB`) 반투명 얇은 엣지 라이트만 그림 — 잡을 수 있는 영역은
    넓게, 보이는 선은 얇게. `/frontend-design`, `superpowers:brainstorming`
    두 스킬로 사용자와 함께 요구사항부터 다시 정리한 뒤 진행한 재설계.
  - **진짜 근본 원인(4번째 시도 후 발견)**: 이 재설계까지 배포했는데도
    사용자가 "테두리도 안 보이고 이동/리사이즈도 안 됨"을 재차 리포트.
    3번 이상 같은 기능에서 실패 = `systematic-debugging` Phase 4.5의
    "아키텍처를 의심하라" 신호라 코드를 더 갈아엎지 않고 먼저 라이브
    스크린샷으로 확인 → **`MiniView`/`ExpandedView`가 순수 `QWidget`인데
    `WA_StyledBackground` 속성을 프로젝트 전체에서 단 한 번도 설정한 적이
    없었음**. Qt에서 이 속성 없이는 `QWidget`의 QSS `background`/`border`가
    전혀 렌더링되지 않음(자식 `QPushButton`은 자기 스타일을 그리니 안
    보였을 뿐) — 이번 라운드가 아니라 애초 Phase 1.5 UI 리디자인 때부터
    있었던 잠재 버그, 이번에 테두리를 실제로 그리려고 하면서 처음
    표면화됨. `MiniView.__init__`/`ExpandedView.__init__`에
    `self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)`
    추가로 해결 — 수정 후 실제 창 스크린샷으로 그라디언트 배경+테두리
    둘 다 렌더링되는 것 확인. 이동/리사이즈 메커니즘 자체는(이미
    off-screen `QMouseEvent` 주입으로 검증됨) 손대지 않고, `window_grip.py`에
    임시 로그를 심어 실제 드래그 입력으로 재검증 — `mousePressEvent`/
    `mouseMoveEvent`가 정확한 zone으로 계속 발화하고 실제 창 geometry가
    비율 유지하며 바뀌는 것까지 로그+`list_windows`로 직접 확인(로그는
    검증 후 원복). 즉 테두리가 안 보였던 것 자체가 "어디를 잡아야 할지
    몰라서" 이동/리사이즈도 실패로 이어진 것으로 보임 — 메커니즘은
    처음부터 정상이었을 가능성이 높음.
  - 비율 고정은 Mini/Expanded 둘 다 항상 적용(사용자 명시적 요청) —
    `MiniView.ASPECT = COLS/ROWS = 2.0`, `ExpandedView.ASPECT = 312/184`.
    `MainWindow._enforce_aspect()`가 두 mixin의 `locked_aspect` 값을 읽어
    사후 보정(`resizeEvent`에서, `_resizing_guard`로 재귀 방지) — 드래그
    자체는 이미 `compute_resized_rect()`가 실시간으로 비율을 지키므로
    이건 OS 스냅 등 외부 요인에 대한 안전망.
- `ui/mini_view.py`: 8패드를 `ui/grid_layout.py`의 `compute_pad_rects()`
  (정사각형 셀 레터박스 배치, 순수 함수, pytest 커버)로 수동 배치.
  `MARGIN=20`, `SPACING=8`. 패드는
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
- `config.py`: `DEFAULT_ACTIONS_PATH`, 모드/테마/always-on-top 영속화
  (`load_last_mode`/`save_last_mode`, `load_last_theme`/`save_last_theme`,
  `load_last_always_on_top`/`save_last_always_on_top`, 전부 `QSettings`,
  테마 기본값은 `"dark"`, always-on-top 기본값은 `False`). Always-on-top은
  트레이/우클릭 메뉴의 체크 가능한 "Always on Top" 항목에서 토글 —
  `MainWindow._apply_always_on_top()`이 `Qt.WindowType.WindowStaysOnTopHint`
  플래그를 set/clear하고, 창이 이미 보이는 상태면 `setWindowFlags` 후
  `show()`를 다시 호출해야 함(Qt 제약 — 플래그 변경 시 창이 hide됨).
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
- Windows 창 제어: `focus_window`(다른 앱 대상)는 기존 구현, mpk-deck
  자체 창의 move/resize/always-on-top(트레이 체크 토글) 모두 구현.
  로드맵 체크리스트 항목 닫음. 2026-08-23 세 차례 재설계 끝에 순수 Qt
  수동 처리(`ui/window_grip.py`)로 정착 — 자세한 경위와 이전 두 시도
  (그립 위치 버그 → 여백 확대 + 커서 → 네이티브 `WM_NCHITTEST`, 셋 다
  실사용 검증에서 실패)는 위 아키텍처 섹션과 `ROADMAP.md` Decision Log
  2026-08-23 항목 참고.
  - `MainWindow`/Qt 위젯은 정책상 pytest 커버 대상이 아니라서, 오프스크린
    스모크 스크립트로 검증: 실제 `QMouseEvent`를 위젯에 직접 주입해서
    (1) 패드 위 호버 시 패드 자체 `PointingHandCursor` 유지(부모 커서
    안 새는지), (2) 코너/변 호버 시 올바른 리사이즈 커서, (3) 배경 갭
    호버 시 `SizeAllCursor`, (4) 코너 드래그로 실제 창 크기가 비율
    유지하며 커짐, (5) 배경 드래그로 실제 창 위치가 이동함 — 다섯 개
    전부 확인. `python -m mpk_deck` 라이브 확인은 아직 사용자 몫(마우스
    누른 상태로 실제 드래그하는 건 자동화로 안전하게 재현하기 어려움).
- 반투명 프레임리스 최상위 창은 `QWidget.grab()`/`render()` 자동 캡처가
  안 됨(Qt 캡처 한계, 자식 위젯 단독 캡처는 정상 — 스타일 자체는 검증됨).
  실제 데스크톱 컴포지팅(DWM)에서 어떻게 보이는지는 `python -m mpk_deck`로
  직접 확인 필요 (사용자 몫, 아직 미확인).
- 자연어 액션 설정 기능은 실제 API 키로 실행 검증 안 됨 — `.env`에
  `ANTHROPIC_API_KEY` 넣고 `python -m mpk_deck`에서 다이얼로그 열어 확인 필요.
- `ExpandedView` UI 다듬기(배경/버튼/노브 스타일, 비율 스케일링, 15백+10흑
  진짜 피아노 건반) 완료 — 2026-08-25 `dbf75b3`로 커밋/푸시, 사용자 라이브
  확인 완료. 자세한 내용은 `ROADMAP.md` Decision Log 2026-08-25 항목 참고.

다음 라운드 — "매일 쓰는 덱" 준비, 서로 독립적인 서브시스템으로 쪼개서
아래 순서대로 진행 (각자 자기 차례에 `superpowers:brainstorming`부터,
코딩 먼저 시작하지 말 것). 성능(CPU/RAM 최소, busy-wait 금지)은 전부에
적용되는 공통 제약이지 별도 항목 아님:

1. **A. MIDI 연결 상태 표시등 + 재연결** — Mini/Expanded 둘 다 뱅크 표시
   옆에 작은 원(연결=초록/미연결=빨강), 미연결일 때 클릭하면 재연결 시도.
   지금은 시작할 때 포트 한 번만 열고 끝(재연결 없음), 트레이 툴팁 텍스트가
   유일한 상태 표시. 작고 독립적이라 먼저 — 나중 하드웨어 연동(F)에도 필요.
2. **B. Bank/프로필 시스템** — 지금 `actions.yaml` 바인딩 맵 하나뿐인 구조를
   다중 뱅크로 확장. 뱅크 전환은 **새 액션 타입(`switch_bank`)으로 만들어서
   아무 컨트롤(패드/버튼/건반 등)에나 바인딩 가능**하게(건반 전용 아님,
   2026-08-25 사용자 확정). 뱅크 이름 사용자 설정 가능, Mini/Expanded 둘 다
   같은 활성 뱅크의 바인딩을 보여줘야 함(동기화), Mini 쪽에는 우측 하단쯤에
   뱅크 표시. 다른 서브프로젝트들이 다 이 구조 위에 올라가므로 A 다음
   최우선.
3. **C. 조이스틱 기본 스크롤 + UI 실제 움직임** — 조이스틱을 기본으로
   가로/세로 스크롤 액션에 매핑, ExpandedView 조이스틱이 실제 밀리는 것처럼
   시각적으로도 움직이게.
4. **D. 액션 타입 확장 + 자연어 설정 커버리지 확대** — 프로그램 실행,
   현재 열린 창 위치/크기 기억해서 나중에 복원(새로운 종류 — 영속 상태
   필요), 노브로 소리/밝기 조절, 쉘 커맨드 실행, 미디어 컨트롤 등. 전부
   `core/nl_action.py` 자연어 설정으로도 커버. 제일 크고 안에서도 더
   쪼개질 수 있음 — B 다음이지만 C/E 이후.
5. **E. 노브 마우스 휠 조작** — ExpandedView 노브 위에서 마우스 휠 돌리면
   해당 노브의 continuous 액션이 값 변경(휠은 델타값이라 절대값 아닌 누적
   로직 필요).
6. **F. 실제 MPK mini MK2 하드웨어 신호 연동** — A~E를 소프트웨어로 먼저
   완성한 뒤 실기로 end-to-end 검증(이 프로젝트 기존 방식과 동일). 이때
   확인 필요한 기존 이슈: `midi/translator.py`가 `pitchwheel` 메시지를
   전혀 처리 안 해서 물리 조이스틱 X축이 무시됨, Y축은 보통 CC1(모드휠)로
   들어오는데 CC1이 지금 `knob_1`에 매핑돼있고 `knob_1`은 `actions.yaml`에서
   `set_system_volume`에 바인딩돼있어 조이스틱을 세로로 밀면 시스템 볼륨이
   바뀔 수 있음(연동 전에 미리 알아둘 것). Bank B 패드 노트(44-51 추정)도
   `PAD_NOTE_TO_CONTROL`에 없어서 지금은 `key_{note}`로 떨어짐 — 새로 만든
   `key_0`~`key_24`(건반)와 노트 번호가 겹치는지 실기로 확인 필요.

**백로그(지금 스코프 아님, 사용자가 명시적으로 나중으로 미룸)**: Windows
시작 시 자동 실행 + 작업표시줄 미표시(트레이 전용).

Phase 2(멀티 모니터, Monitor Manager, Workspace Profiles)는 3.5" 미니
모니터 구매 전까지 착수하지 말 것.

사전 설계 문서: `docs/superpowers/specs/2026-08-17-phase1-mvp-design.md`,
계획: `docs/superpowers/plans/2026-08-17-phase1-mvp.md`,
`docs/superpowers/specs/2026-08-19-nl-action-config-design.md` +
`docs/superpowers/plans/2026-08-19-nl-action-config.md`.
