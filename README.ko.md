# Nuke Viewer Clipboard

현재 Viewer 프레임을 **출력 해상도 그대로 클립보드에 복사**하는 Nuke 플러그인입니다. **Ctrl+Alt+C**로 복사하고, 이미지를 지원하는 앱에 붙여넣을 수 있습니다.

[English](README.md) · [다운로드](https://github.com/tardis7732/nuke-viewer-clipboard/releases/latest)

## 주요 기능

- 활성 Viewer의 기본 입력과 현재 프레임을 사용합니다.
- Reformat을 포함한 연결 노드의 출력 크기를 따릅니다.
- Viewer 확대·이동과 관계없이 전체 프레임을 복사하며, UI 여백과 오버레이는 포함하지 않습니다.
- Viewer Process와 Viewer의 gain·gamma·saturation 설정을 적용합니다.
- 클립보드에는 불투명한 8비트 RGB 이미지와 PNG 데이터를 넣습니다.
- 현재 한 프레임만 임시 PNG로 렌더하고, 이미지를 읽은 뒤 임시 폴더를 삭제합니다.

예를 들어 **1920 × 1080 Reformat**을 Viewer에 연결하면 복사되는 이미지도 **1920 × 1080**입니다. 영상 자체에 포함된 레터박스는 유지됩니다.

## 설치

**Windows / Nuke 17.1v1에서 확인했습니다.** Nuke에 포함된 Python과 Qt를 사용하므로 추가 패키지 설치는 필요하지 않습니다. 다른 운영체제와 Nuke 버전은 검증하지 않았습니다.

1. 최신 릴리스를 내려받아 압축을 풉니다.
2. `NukeViewerClipboard` 폴더를 `.nuke` 폴더에 복사합니다. Windows 탐색기 주소창에 `%USERPROFILE%\.nuke`를 입력하면 해당 위치가 열립니다.
3. `.nuke/init.py`에 아래 코드를 추가합니다. 파일이 없으면 새로 만들고, 기존 내용이 있으면 유지합니다.

   ```python
   import nuke
   nuke.pluginAddPath("./NukeViewerClipboard")
   ```

4. Nuke를 다시 실행합니다.

배포 파일의 `menu.py`는 `NukeViewerClipboard` 폴더 안에 그대로 둡니다. 기존 `.nuke/menu.py`를 덮어쓰지 마세요.

## 사용법

1. 원하는 노드를 Viewer에 표시하고 복사할 프레임에서 정지합니다.
2. **Ctrl+Alt+C**, 또는 **Viewer → Copy Frame to Clipboard**를 실행합니다.
3. 한 프레임 렌더가 끝나면 원하는 앱에서 **Ctrl+V**로 붙여넣습니다.

복사가 완료되면 프레임 번호와 이미지 크기가 툴팁으로 표시됩니다. 처리 시간은 연결된 노드 그래프에 따라 달라집니다. 렌더를 취소하면 기존 클립보드 내용이 유지됩니다.

### 단축키 변경

`NukeViewerClipboard/menu.py`에서 원하는 조합을 지정합니다.

```python
import copy_viewer_frame

copy_viewer_frame.register(shortcut="Ctrl+Alt+C")
```

기존 단축키와 겹치지 않는 조합을 선택한 뒤 Nuke를 다시 실행합니다. 실행 중인 세션에서는 위 두 줄을 Script Editor에서 실행해 바로 바꿀 수 있습니다.

## 파일 처리

복사할 때 proxy를 잠시 끄고, 임시 노드에서 연결된 그래프의 한 프레임을 전체 해상도로 렌더합니다. 완료 후 선택 상태·프레임·proxy·스크립트 수정 표시를 복구하며 undo 단계는 추가하지 않습니다.

PNG는 운영체제 임시 경로의 `nuke_viewer_clipboard_*` 폴더에 생성됩니다. 이미지를 읽은 뒤 폴더를 삭제하며, 렌더 실패나 취소 시에도 정리합니다. 원본 영상 옆이나 프로젝트 폴더에는 파일을 저장하지 않습니다. Nuke가 강제 종료되면 임시 파일이 남을 수 있습니다.

## 지원 범위

- 출력은 표시용 8비트 이미지입니다. 알파 투명도와 부동소수점 HDR 값은 보존하지 않습니다.
- Viewer의 A/B 와이프·비교 모드·3D 뷰·마스크·오버레이는 재현하지 않으며 기본 입력을 복사합니다.
- RGB 및 R/G/B/A/Y 채널 표시를 지원합니다. 다른 채널 표시 모드는 오류 안내 후 중단합니다.
- `Group`으로 구성한 사용자 정의 Viewer Process는 지원하지 않습니다. 단일 입력 Input Process 노드·Group은 복사할 수 있지만, 외부 연결이나 상대 경로 표현식에 의존하는 설정은 별도 출력 구성이 필요할 수 있습니다.
- 붙여넣은 앱의 색상 관리에 따라 표시 결과가 달라질 수 있습니다.

## 삭제

`.nuke/init.py`에서 추가한 `pluginAddPath` 줄을 지우고 `NukeViewerClipboard` 폴더를 삭제한 뒤 Nuke를 다시 실행합니다.

## 라이선스

[MIT](LICENSE)
