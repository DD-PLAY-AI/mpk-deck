---
card:
  what: "AKAI 버튼과 노브로 PC 작업을 빠르게 실행하게 한다"
  stage: "기능을 갖추고 실제 기기에서 확인하는 단계"
  can_do:
    - "패드와 건반으로 프로그램·웹페이지·창을 조작한다"
    - "노브로 소리·화면 밝기·스크롤을 조절한다"
    - "말로 설명한 동작을 버튼 설정으로 제안받는다"
  not_yet: "실제 기기에서 한 번도 끝까지 확인하지 않아, 일상에서 바로 쓸 수 있는지 모른다"
---

# CONTEXT.md — mpk-deck

아키텍처(코드 기준), 기술 스택, 하드웨어 MIDI 매핑, 현재 진행 상태(A~F).
프로젝트 규칙·정체성은 `CLAUDE.md`, 워크스페이스 공통은 `C:\DC\DD\CLAUDE.md`
+ `C:\DC\DD\ROADMAP.md`(결정 이력은 `C:\DC\DD\docs\decisions\mpk-deck.md`, 인덱스 `docs\DECISIONS.md`).

이 파일은 모든 에이전트(Claude·Codex) 공용이다. mpk-deck 코드 작업 전에 읽을 것.

> **드리프트 주의 (2026-09-02/03):** 하드웨어 MIDI 매핑 섹션 + 아래 Workspace
> Layouts 항목은 갱신됨(신뢰). 그러나 이 파일의 **UI 상세 서술 일부는 아직
> 2026-09-02 batch B/C 이전 상태**를 설명한다 — 실제로는:
> - `ui/action_config_dialog.py`는 프레임리스 글래스 "patch card"로 전면
>   재작성됨(painted `_ControlChip`, 아이콘 타일 액션 픽커, sensitivity 슬라이더,
>   접이식 NL 섹션). `_dialog_qss(accent_hex, dark)` 공유.
> - `ui/action_icons.py`는 `{accent}`/`{neutral}` SVG 템플릿 + `QSvgRenderer`
>   (QPainter 글리프 함수 폐기). `_ACTION_SVG`/`_ACTION_SVG_KNOB`.
> - trigger flash는 성공/실패 초록·빨강이 아니라 하드웨어 입력 시 마우스
>   클릭과 같은 accent glow(`flash()`, `ok` 없음). knob_1 `_locked` 배선 전부 삭제.
> - `Binding`에 `label`(사용자 지정 이름) + `icon`(커스텀 SVG body) 필드.
>   `MiniView`/`ExpandedView.update_bindings(bindings, bank_names, layouts)`.
> - `core/icon_gen.py`(Claude Haiku SVG 아이콘 + `is_safe_svg_body` denylist).
> - E: `KnobWidget.wheelEvent`(휠 → 값 누적) → `ExpandedView.knob_scrolled` →
>   `MainWindow._on_knob_scrolled` → `engine.set_continuous`.
>
> **batch B/C/D/E 전부 `main`에 머지·푸시 완료(2026-09-05, `origin/main`과 동기).
> 실기 미검증.** 변경의
> 배경·근거는 `C:\DC\DD\docs\decisions\mpk-deck.md` 2026-09-02 항목. 코드가 최종
> 신뢰원. 실기 검증 후 이 파일 UI 상세를 전면 갱신할 것.

---

## 실제 아키텍처 (코드 기준)

- `core/action_engine.py`의 `ActionEngine`이 유일한 실행 진입점.
  `register_trigger`/`register_continuous`로 액션 이름 -> 핸들러 함수를
  등록하고, `load_banks(banks: dict[str, list[Binding]], switch_bindings:
  dict[str, str], active_bank: str)`로 뱅크별 바인딩을 적재한다. 생성자에
  선택적 `on_bank_changed: Callable[[str], None]`, `on_continuous:
  Callable[[str, float], None]`, `on_trigger: Callable[[str, bool], None]`
  콜백(전부 옵션)을 받는다. `on_continuous`는 `set_continuous()`가 호출될
  때마다 바인딩 존재 여부와 무관하게 무조건 발화 — UI가 하드웨어 입력을
  시각적으로 미러링(조이스틱 손잡이, 노브 바늘)할 수 있게 해주는 용도.
  `on_trigger`는 등록된 핸들러가 실행된 뒤 발화(`(control, ok)` — 핸들러
  예외는 `trigger()`가 잡아서 `ok=False`, 정상 반환은 `ok=True`, `switch_bank`
  는 `ok=True`; 바인딩/핸들러 없으면 발화 안 함) — UI가 패드·건반에 성공=
  초록/실패=빨강 플래시를 주는 용도. 둘 다 실제 액션 디스패치와는 별개 경로. `switch_bank
  (bank_id)` 메서드와 `active_bank` 프로퍼티를 노출. `trigger()`가
  `switch_bank` 액션을 직접 인식해서 `self.switch_bank(...)`를 호출 —
  `switch_bank`는 `handlers.py`에 등록되는 일반 핸들러가 아니라 엔진 내재
  개념. MIDI 콜백과 UI 클릭 둘 다 `engine.trigger(control)` /
  `engine.set_continuous(control, value)`만 호출하고, 직접 실행하지 않는다.
- `core/action_registry.py`: `load_config`/`save_config`이 `config/
  actions.yaml`을 로드/저장하는 `DeckConfig`(`active_bank`,
  `switch_bindings`, `banks: dict[str, Bank]` — `Bank`는 `name`/`bindings`)
  기반 API. `load_config`는 절대 예외를 던지지 않음 — 파일 없음, YAML 파싱
  에러, 구조가 잘못된 경우 모두 단일 뱅크 기본 설정으로 폴백. 잘못된
  개별 바인딩은 로그 후 skip. `ActionConfigError`는 더 이상 없음.
- `core/handlers.py`: 실제 side-effect 핸들러 (`launch_program`,
  `open_url`, `focus_window`, `set_system_volume`, `scroll_horizontal`/
  `scroll_vertical` — 진짜 `win32api.mouse_event` 휠 주입, 합성
  `PostMessage` 아님), `set_display_brightness`(continuous, WMI 내장 패널,
  약 3 Hz throttle, `_BRIGHTNESS_MIN_INTERVAL_S=0.3`), `run_shell_command`(trigger, `shell=True`
  fire-and-forget), `media_key`(trigger, `keybd_event` VK_MEDIA_*). 트리거 핸들러는
  `(params: dict) -> None`, continuous 핸들러는
  `(params: dict, value: float) -> None` 시그니처를 따른다. Windows 전용
  의존성(`win32gui`, `pycaw`)은 함수 내부에서 지연 import — 모듈 로드
  자체는 해당 패키지 없이도 가능해야 한다.
- `core/program_finder.py`: 시작 메뉴 `.lnk` 스캔해서 설치된 프로그램
  목록 제공 (프로그램 런처 UI용).
- MIDI 흐름: `midi/mpk_controller.py`의 `MPKController`가 `mido`로 MPK
  mini MK2 포트를 열고 콜백 기반으로 리슨 (폴링 없음) -> 각 메시지를
  `midi/translator.py`의 `translate()`(순수 함수, MIDI note/CC/pitchwheel ->
  `ControlEvent`)로 변환 -> `ActionEngine.trigger`/`set_continuous` 호출.
  **하드웨어 확정 매핑(2026-09-02 재캡처 — F의 2026-08-29 가정이 이 유닛엔
  틀렸음)**: 패드 note **32-39** -> `pad_1`..`pad_8`(사용자가 이 note를 보내는
  패드 뱅크로 고정), 건반 note 48-72 -> `key_0`..`key_24`(`note-48`,
  `KEYBED_BASE_NOTE`/`KEYBED_KEY_COUNT` 상수), 노브 **CC 2-9 -> `knob_1`..
  `knob_8`**(`{cc: f"knob_{cc-1}"}`), `pitchwheel` -> `joystick_x`,
  **CC 1 -> `joystick_y`(전용)**. Y축은 이 프리셋에서 **unipolar**: 정지=0,
  최대=127 한 방향, `value/127`로 [0.0,1.0] 디코딩(bipolar `(v-64)/64` 아님).
  MainWindow가 `JOYSTICK_DEADZONE=0.06` 미만은 0으로 스냅(스프링 팟 지터 +
  재캡처 오류 시 idle 스크롤 폭주 방지).
  **⚠️ 이 매핑은 장치에 커스텀 AKAI 에디터 프리셋이 로드/저장돼 있어야 성립.**
  노브 1-8을 CC 2-9로 시프트(팩토리는 CC 1-8), 그래서 CC 1이 조이스틱 Y 전용.
  팩토리 상태나 다른 호스트/공장 초기화 후엔 노브가 1칸씩 밀리고 노브 1이 CC1로
  조이스틱을 움직인다 — 코드는 이 불일치를 감지/경고하지 않음. 조이스틱 Y
  bipolar 전환도 에디터 작업 대기 중(spec Open Question).
  건반 범위 밖(옥타브 시프트) 노트와 그 외 note/CC는
  `None`으로 drop — 패드가 32-39라 옥타브 다운 시 저음 건반이 이 범위와 겹칠 수
  있음(문서화된 제약, 사용자가 OCT 버튼 안 씀). `translate()` 외에
  `is_bank_b_pad_note(message)` 순수 함수 — note_on 44-47(다른 패드 뱅크의
  저음역, "패드를 되돌려라" 힌트용)이면 True.
  `MPKController` 생성자의 `on_bank_b_pad` 콜백이 이걸로 발화 -> MainWindow가
  "Bank A로 전환" 배너 표시.
- `MPKController`는 생성자에 `on_bank_b_pad: Callable[[], None]`(옵션)도
  받는다. 장치 언플러그 시 rtmidi WinMM 포트를 `close()`하면 C 레벨에서
  프로세스가 죽으므로, `poll_connection`이 장치 소실을 감지하면 포트를
  `close()` 없이 모듈 레벨 `_ABANDONED_PORTS`에 넣고 버린다(재연결 시 새 포트).
- `config/actions.yaml`이 바인딩의 source of truth, 뱅크 인식 구조로
  확장됨. 손으로 수정하거나 `ui/action_config_dialog.py`의 GUI로 수정 —
  둘 다 같은 `load_config`/`save_config`를 거친다.
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
  `pad_configure_requested -> ActionConfigDialog` 로 각각 연결. `PadButton`은
  눌렀을 때 accent 색 `QGraphicsDropShadowEffect` glow를 낸다.
  `MiniView.set_accent(accent_hex)`가 모든 패드와 패널 테두리에 전파.
- 테마: `set_dark(bool)`로 Light/Dark 전환. Light는 실제로 반투명(흰색
  글래스, 어두운 텍스트), Dark는 어두운 글래스 배경에 밝은 텍스트
  (`#f2f4f8`, 이전엔 `#d7dae0`라 잘 안 보였음 — 가독성 때문에 밝게 조정).
  `ExpandedView`는 이번 라운드에서 테마 손 안 댐(레이블 잘림만 수정),
  다음 UI 라운드 대상.
- `ui/expanded_view.py`의 `JoystickWidget` — 오랫동안 배경/테두리가 전혀
  그려지지 않던 버그가 여기도 있었음(`WA_StyledBackground` 미설정, 위
  Mini/ExpandedView와 같은 근본 원인). 속성 추가로 고치면서 "소켓 +
  광택 있는 구형 손잡이" 그라디언트 디자인으로 다시 그림. 같은 파일의
  `KnobWidget(QFrame)`이 기존 평범한 `QLabel` 노브 8개를 대체 —
  `ui/knob_geometry.py`의 `needle_angle()`로 실시간 값을 그리는 두 스타일
  지원: `"A"`(숫자 유지 + 작은 점이 궤도를 도는 방식), `"B"`(숫자 없이
  풀 니들만). `ExpandedView.set_knob_style(style)`/`set_accent(accent_hex)`
  로 전환. **F(2026-08-29)**: `KnobWidget`에 더블클릭 처리 추가 —
  `configure_requested`/`blocked_configure_requested` 시그널. knob 2~8은
  `ExpandedView.control_configure_requested`로 이어지고, knob_1(label `"1"`,
  `_locked=True`)은 `ExpandedView.knob_locked_activated`로 이어져 MainWindow가
  "사용할 수 없습니다" 안내. knob_1은 비활성(회색)으로 표시. `PadButton`과 `_DebouncedKey`에
  `flash(ok: bool)` 추가(재사용 `QTimer`로 ~200ms 초록/빨강 글로우) —
  `MiniView.flash_control(control, ok)` / `ExpandedView.flash_control(control, ok)`가
  MainWindow의 `on_trigger` 콜백에서 호출됨.
- **F: 함수 버튼은 장식용**. `ExpandedView`의 `LEFT_BUTTONS`+`RIGHT_BUTTONS`
  10개(arp/tap/oct▼/oct▲/full/rpt, bank_ab/cc/prog_change/prog_select)는
  MK2가 MIDI를 안 보내므로 `DECORATIVE_CONTROLS`로 묶여 액션 배선 없음 +
  흐린 스타일. 더블클릭하면 `decorative_button_activated(control)` 시그널 ->
  MainWindow가 `QMessageBox`로 "MIDI 전송 안 함, 설정 불가" 안내.
- `ui/bank_hint.py`의 `BankHint(QLabel)` — `is_bank_b_pad_note`가 감지되면
  MainWindow가 `show_hint()` 호출, 상단 중앙에 "패드를 Bank A로 전환" 배너를
  ~4초 표시 후 자동 숨김(`_hide_timer`). `BankIndicator`/`MidiStatusDot`과
  같은 `MainWindow` 오버레이 패턴, `set_accent(accent_hex)`.
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
  "Add Bank" 액션을 선택하면 그 컨트롤을 `switch_bank`에 영구 고정 —
  이후 그 컨트롤을 다시 열면 다른 액션 항목이 전부 비활성화되고 뱅크
  이름만 수정 가능.
- `ui/bank_indicator.py`의 `BankIndicator` — 활성 뱅크 이름을 표시,
  `ui/midi_status_dot.py`의 `MidiStatusDot`과 같은 `MainWindow` 오버레이
  위젯 패턴. 불투명 accent 배지로 렌더링 — `set_dark`는 완전히 삭제됐고,
  외형을 바꾸는 유일한 메서드는 `set_accent(accent_hex)`(아래 디자인
  설정 참고).
- `ui/accent.py`: 7개의 선택 가능한 accent 색상(`ACCENT_CHOICES`)과
  `mix()`/`hex_to_rgb_str()` 색상 연산 순수 함수. `ui/knob_geometry.py`:
  `needle_angle(value)` — 노브 값을 7시~5시(12시를 지나 시계방향 300°)
  스윕 각도로 변환하는 순수 함수. 둘 다 pytest 커버.
- `config.py`: `DEFAULT_ACTIONS_PATH`, 모드/테마/always-on-top 영속화
  (`load_last_mode`/`save_last_mode`, `load_last_theme`/`save_last_theme`,
  `load_last_always_on_top`/`save_last_always_on_top`, 전부 `QSettings`,
  테마 기본값은 `"dark"`, always-on-top 기본값은 `False`). Always-on-top은
  트레이/우클릭 메뉴의 체크 가능한 "Always on Top" 항목에서 토글 —
  `MainWindow._apply_always_on_top()`이 `Qt.WindowType.WindowStaysOnTopHint`
  플래그를 set/clear하고, 창이 이미 보이는 상태면 `setWindowFlags` 후
  `show()`를 다시 호출해야 함(Qt 제약 — 플래그 변경 시 창이 hide됨). 같은
  `QSettings` 패턴으로 `load_last_accent`/`save_last_accent`,
  `load_last_knob_style`/`save_last_knob_style` 추가(디자인 설정, 아래
  참고).
- `core/nl_action.py`: `parse_nl_action(text, installed_programs, client=None)
  -> Binding | None`. Claude Haiku 4.5를 tool_choice로 강제해 구조화 출력만
  받음 — `launch_program`은 모델이 고른 프로그램 이름이 실제 설치 목록에
  정확히 일치할 때만 허용(없는 경로 지어내는 것 차단). `client` 주입 가능
  (`handlers.py`의 `finder`/`volume_setter` 패턴과 동일), 실패/모호하면
  항상 `None`. `ANTHROPIC_API_KEY`는 `.env`(gitignored)에서
  `python-dotenv`로 `__main__.py`가 앱 시작 시 로드 — 앱 내 키 입력 UI 없음.
  `action_config_dialog.py`가 이 함수 호출 결과로 기존 폼 필드만 채움,
  저장은 여전히 사용자가 Save를 눌러야 함. `apply_layout`(레이아웃 이름 →
  layout id)도 커버.

- **Workspace Layouts** (`core/layout_store.py` + `core/window_layout.py` +
  `core/browser_url.py` + `apply_layout` 핸들러 + `ui/layout_capture_dialog.py`,
  spec/plan `docs/superpowers/{specs,plans}/2026-09-02-workspace-layouts*`):
  한 패드가 프로그램 + 브라우저 사이트 여러 개를 저장된 위치·크기로 연다.
  - 레이아웃 = `%APPDATA%\mpk-deck\layouts.yaml`(`config.LAYOUTS_PATH`,
    `config.user_data_dir()`)의 named 항목 리스트. 항목 = `kind: program|url`,
    `rect`(x/y/w/h 물리px), `maximized`, `title_match`. `load_layouts`/
    `save_layouts`(atomic, `allow_unicode`)/`generate_layout_id`는
    `action_registry` 패턴 복사.
  - `apply_layout` 트리거 핸들러가 layout을 로드하고 `restore_layout`을
    **데몬 스레드**에서 실행(앱 실행·창 폴링이 수 초 걸려서 GUI 스레드 블록
    금지). 이미 열린 창은 `match_window`로 찾아 재배치(중복 실행 안 함),
    없으면 실행 후 창 뜰 때까지 폴링 → `position_window`(보이는 모니터
    work-area로 clamp, 브라우저 post-show relayout 대비 두 번 배치).
  - `list_open_windows`/`capture_item`/`position_window`는 win32 직접,
    `restore_layout`/`match_window`/`clamp_rect_to_monitors`는 seam 주입 +
    pytest 커버. `browser_url.active_tab_url`는 UIA(`comtypes`, 새 dep 없음)
    best-effort — Chrome/Edge 확인, Firefox best-effort, 실패 시 None →
    capture 다이얼로그의 수동 URL 필드가 폴백. Edge에서 라이브 검증됨.
  - config 다이얼로그: "레이아웃" 액션(드롭다운 + 새로 저장…/편집… →
    `LayoutCaptureDialog`, 열린 창 체크리스트). `Binding.label`/`icon`은 이
    액션에도 적용됨(switch_bank과 달리 잠기지 않음).
  - **미완**: `config/actions.yaml` + `QSettings`를 `user_data_dir()` 아래로
    옮기는 마이그레이션(별도 태스크). 조이스틱 Y bipolar Editor 작업.

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

## 현재 진행 상태

날짜별 진행 기록은 archive 로 옮김 → [2026-09-20-context-diet.md](docs/archive/2026-09-20-context-diet.md#현재-진행-상태)
