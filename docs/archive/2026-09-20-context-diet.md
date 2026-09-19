← 돌아가기: [CONTEXT.md](../../CONTEXT.md) — 2026-09-20 CONTEXT 다이어트(T-0071)로 옮김, 원문 그대로

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
  실사용 검증에서 실패)는 위 아키텍처 섹션과 `C:\DC\DD\docs\decisions\mpk-deck.md`
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
  확인 완료. 자세한 내용은 `C:\DC\DD\docs\decisions\mpk-deck.md` 2026-08-25 항목 참고.

다음 라운드 — "매일 쓰는 덱" 준비, 서로 독립적인 서브시스템으로 쪼개서
아래 순서대로 진행 (각자 자기 차례에 `superpowers:brainstorming`부터,
코딩 먼저 시작하지 말 것). 성능(CPU/RAM 최소, busy-wait 금지)은 전부에
적용되는 공통 제약이지 별도 항목 아님:

1. ~~**A. MIDI 연결 상태 표시등 + 재연결**~~ — **완료, 2026-08-25/26 실기
   검증까지 끝남.** `MainWindow` 오버레이 위젯(Mini/Expanded 공용) + 초록/
   빨강 점, 클릭 또는 3초 타이머로 `MPKController.poll_connection()` 호출.
   실기 검증 중 버그 3개 발견/수정(전부 커밋됨): 미연결 상태에서 폴링마다
   경고 로그가 반복 출력되던 문제(`06435d5`), ExpandedView 라이트 테마가
   MiniView와 다른 하늘색 배경이던 문제(`b678faf`), 트레이 Quit이 창만
   숨기고 프로세스는 안 끝나던 문제 — `MainWindow`가 `Qt.WindowType.Tool`
   이라 `quitOnLastWindowClosed` 대상에서 제외되는 게 원인, `QApplication.
   quit()` 직접 호출로 수정(`3060b89`). 부수적으로 `python-rtmidi`(선택
   익스트라 `midi-hardware`) 설치 완료 — 빌드에 C++ 컴파일러가 필요해서
   Visual Studio 2022 Build Tools(C++ workload)를 winget으로 설치했고,
   meson이 MSVC를 찾으려면 `vswhere.exe`가 PATH에 있어야 함(설치 위치:
   `C:\Program Files (x86)\Microsoft Visual Studio\Installer`). 이제 이
   환경에서 `mido.get_input_names()`가 실제 장치를 정상적으로 반환함.
2. ~~**B. Bank/프로필 시스템**~~ — **완료, 2026-08-27.** `config/actions.yaml`
   스키마를 `active_bank`/`switch_bindings`/`banks`(뱅크별 `name`+`bindings`)
   구조로 확장 — 기존 flat `bindings:` 포맷 파일은 `load_config`가 자동
   마이그레이션(파일 자체는 다음 저장 때까지 안 건드림). 뱅크 전환은 전역
   `switch_bindings`(컨트롤→뱅크id, 아무 컨트롤에나 바인딩 가능, 2026-08-25
   확정)로 구현 — `ActionEngine.trigger()`가 `switch_bank` 액션을 만나면
   등록된 핸들러 대신 엔진 자체 `switch_bank()`를 직접 호출(엔진 내재
   개념, `handlers.py`에 없음). `ActionConfigDialog`에 "Add Bank" 액션
   추가 — 선택하면 이름만 입력받아 그 자리에서 뱅크 생성+해당 컨트롤을
   `switch_bindings`에 고정 등록, 이후 그 컨트롤은 다른 액션으로 재할당
   불가(액션 리스트에서 다른 항목 전부 비활성화, 뱅크 이름만 수정 가능).
   신규 `ui/bank_indicator.py`(`BankIndicator`) — `MidiStatusDot`과 같은
   `MainWindow` 오버레이 패턴, MIDI 상태 점 옆에 배치, Mini/Expanded 자동
   동일 표시, 라이트/다크 테마 색 전환. `subagent-driven-development`로
   6개 태스크 실행(스펙: `docs/superpowers/specs/2026-08-27-bank-profile-
   system-design.md`, 계획: `docs/superpowers/plans/2026-08-27-bank-
   profile-system.md`), 107/107 테스트 통과. **GUI 상호작용 부분(Add
   Bank 플로우 실제 클릭, 잠금 확인, 뱅크 표시 실시간 갱신, 재시작 후
   유지)은 서브에이전트가 마우스/스크린샷 도구가 없어서 검증 못 함 —
   사용자 라이브 확인 필요.**
3. ~~**C. 조이스틱 기본 스크롤 + UI 실제 움직임**~~ — **완료, 2026-08-28.**
   `midi/translator.py`가 `pitchwheel`(X축)과 새 `JOYSTICK_Y_CC=1`(Y축,
   `KNOB_CC_TO_CONTROL`보다 먼저 체크 — CC1이 실제로 겹치면 조이스틱이
   이김, `knob_1`은 그 CC로 도달 불가해짐, 의도적 선택)을 `joystick_x`/
   `joystick_y` continuous 컨트롤로 디코딩. `ActionEngine`에 `on_continuous`
   콜백 추가(바인딩 여부 무관하게 항상 발화 — 나중에 시각 미러링용).
   `core/handlers.py`의 `scroll_horizontal`/`scroll_vertical`이 진짜
   `win32api.mouse_event` 휠 주입(합성 `PostMessage` 아님 — Chrome류가
   무시하는 거 피함). 마우스로 조이스틱을 드래그하면 `JoystickWidget`
   손잡이만 움직이고 절대 `ActionEngine`을 안 건드림(커서가 mpk-deck
   자기 창 위에 있어서 실제 스크롤을 부르면 자기 자신이 스크롤됨) —
   실제 스크롤은 하드웨어 입력에서만. `MainWindow`가 20Hz 반복 타이머로
   "누르고 있으면 계속 스크롤" 구현(꺾인 축이 있을 때만 돌고 유휴 시
   0). 새 뱅크는 전부 `joystick_x`/`joystick_y`가 기본으로
   `scroll_horizontal`/`scroll_vertical`에 바인딩된 채로 시작(기존 뱅크도
   `load_config`가 없는 것만 채워넣음, 비파괴적). `subagent-driven-
   development`로 8개 태스크 실행(스펙: `docs/superpowers/specs/
   2026-08-28-joystick-scroll-design.md`, 계획: `docs/superpowers/plans/
   2026-08-28-joystick-scroll.md`), 148/148 테스트 통과. **Task 8(MainWindow
   배선)의 태스크 리뷰는 사용자 요청으로 서브에이전트 디스패치 없이
   완료 처리 — 사용자가 직접 라이브로 검증할 예정.** 아직 실기로 확인
   안 된 것(스펙의 Open Questions): 진짜 `JOYSTICK_Y_CC` 값과 `knob_1`
   충돌 여부, `SendInput` 기반 스크롤이 실제 앱(Chrome/카카오톡 등)에서
   먹히는지.

**애드혹 삽입 — 디자인 설정(accent 색 + 노브 스타일), 2026-08-29, A-F
목록에는 없던 항목**: C의 라이브 테스트 도중 발견한 실제 버그 두 개
(`BankIndicator`의 반투명 글래스 필이 다크 모드에서 안 읽힘, `WA_
StyledBackground` 누락으로 `JoystickWidget` 손잡이가 원이 아니라 사각형으로
렌더링됨)에서 시작 — 제대로 고치려다 사용자와 인터랙티브 HTML 목업(세션 중
Artifact로 게시)으로 디자인을 다시 잡는 쪽으로 커졌고, 최종적으로 선택
가능한 accent 색 7종 + 노브 시각 스타일 2종(둘 다 목업이 아니라 실제 구현/
배포됨)이 `QSettings`로 영속되고, 기존 트레이 컨텍스트 메뉴에 새 "Design"
서브메뉴로 노출되는 기능으로 완성. 8개 태스크 전부 리뷰 통과(사소한 항목만,
전부 스펙 범위 안) 후 `main`에 머지. **의도적 예외 한 가지**: 키보드 검은건반
테두리 색은 여전히 리터럴 `config.ACCENT_RGB` 상수에 고정 — 사용자가 명시적
요청한 유일하게 새 accent 설정이 안 닿는 지점. 스펙:
`docs/superpowers/specs/2026-08-29-design-preferences.md`, 계획:
`docs/superpowers/plans/2026-08-29-design-preferences.md`. 아직 라이브 확인
안 된 것: 앱 재시작 후 Design 메뉴 선택값 유지, 실제 MPK mini MK2 노브를
돌렸을 때 화면 인디케이터가 실시간으로 따라오는지.
4. **D. 액션 타입 확장 + 자연어 설정 커버리지 확대** — 프로그램 실행,
   현재 열린 창 위치/크기 기억해서 나중에 복원(새로운 종류 — 영속 상태
   필요), 노브로 소리/밝기 조절, 쉘 커맨드 실행, 미디어 컨트롤 등. 전부
   `core/nl_action.py` 자연어 설정으로도 커버. 제일 크고 안에서도 더
   쪼개질 수 있음 — B 다음이지만 C/E 이후.
   - **D-rest(밝기 / 셸 명령 / 미디어 키 + NL)는 구현·커밋 완료, 하드웨어
     미검증.** 사용자 라이브 확인: 실제 내장 패널 밝기 변경, 미디어 키가
     실제 플레이어에 도달하는지, 실제 API 키로 NL 다이얼로그가 세 액션을
     모두 제안하는지. 밝기는 continuous-dispatch 경로에서 `win32com` COM을
     사용하므로, 아직 열린 volume-knob 버그와 같은 공유 위험이 있다.
5. **E. 노브 마우스 휠 조작** — ExpandedView 노브 위에서 마우스 휠 돌리면
   해당 노브의 continuous 액션이 값 변경(휠은 델타값이라 절대값 아닌 누적
   로직 필요).
4b. **E. 노브 마우스 휠 조작** — 위 5번. 참고: 디자인 설정 라운드(2026-08-29)에서
   `KnobWidget`이 실시간 값 인디케이터로 이미 재작성됨. F에서 knob_1 더블클릭 차단 +
   knob 2~8 더블클릭 설정이 추가됨(스펙/플랜 2026-08-29). E는 여기에 휠 델타 누적만
   얹으면 됨 — 재스코프 필요.
6. ~~**F. 실제 MPK mini MK2 하드웨어 신호 연동**~~ — **완료, 2026-08-29.**
   실기 캡처(`scratchpad/midi_monitor.py`)로 팩토리 MIDI 맵 확정 후 에디터
   변경 없이 연동. 최종 매핑: `pitchwheel`→`joystick_x`, `CC1`→`joystick_y`,
   `knob_1`은 MIDI 매핑 없는 비활성(회색) 노브이며 더블클릭 시 "사용할 수 없습니다" 안내,
   `CC2~8`→`knob_2~8`, `note 36~43`→`pad_1~8`(패드는 사용자가
   Bank A 유지), `note 48~72`→`key_0~24`(`note-48`), `note 44~47`→이벤트 없음 +
   "Bank B → Bank A 전환" 배너. 함수 버튼 10개(OCT/ARP/TAP/FULL/RPT/CC/
   CHG/SEL/BANK 등)는 MIDI를 전혀 안 보냄 → `ExpandedView`에서 비활성 스타일 +
   더블클릭 시 "설정 불가" 안내. `ActionEngine`에 `on_trigger(control, ok)`
   콜백 추가 → 패드·건반 성공=초록/실패=빨강 플래시. `translator.py`가 건반
   범위 밖(옥타브 시프트) 노트는 drop(기본 옥타브 가정, 문서화된 제약).
   `superpowers:subagent-driven-development`로 9개 태스크(스펙:
   `docs/superpowers/specs/2026-08-29-hardware-wiring-design.md`, 계획:
   `docs/superpowers/plans/2026-08-29-hardware-wiring.md`), 182 테스트 통과.
   **실기 end-to-end 검증(모든 패드/건반/노브2~8/조이스틱 축, 함수 버튼 무반응,
   실패 시 빨강 플래시, Bank B 배너)은 사용자 몫 — 아직 미확인.**

**F 범위 밖 → 향후 라운드로 이월(로드맵 참고)**: Bank별 기능 유지/상속 옵션,
기능표시 옵션(글자/생략/아이콘) 컨트롤별, 마우스 호버 툴팁, 패드 아이콘
디자인(앱 아이콘 추출 등), 여러 건반 동시 입력(chord).

**백로그(지금 스코프 아님, 사용자가 명시적으로 나중으로 미룸)**: Windows
시작 시 자동 실행 + 작업표시줄 미표시(트레이 전용).

Phase 2(멀티 모니터, Monitor Manager, Workspace Profiles)는 3.5" 미니
모니터 구매 전까지 착수하지 말 것.

사전 설계 문서: `docs/superpowers/specs/2026-08-17-phase1-mvp-design.md`,
계획: `docs/superpowers/plans/2026-08-17-phase1-mvp.md`,
`docs/superpowers/specs/2026-08-19-nl-action-config-design.md` +
`docs/superpowers/plans/2026-08-19-nl-action-config.md`.


