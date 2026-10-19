# CoinDemo 핸드오프

언리얼 엔진 5.8로 만든 3인칭 코인 수집 게임입니다. 스테이지의 코인을 모두 모으면 다음 스테이지로 넘어가고,
2~5스테이지는 ANNX 3D 가우시안 스플래팅(3DGS) 실사 스캔을 그대로 맵으로 씁니다. 주인공은 MetaHuman입니다.

마지막 상태 (2026-10-20): 5개 스테이지 처음부터 끝까지 플레이 가능, RTX 5080에서 120~300fps.
코드 저장소: https://github.com/JJleem/unreal-coin (코드, 스크립트, 설정, 문서만. 에셋은 로컬)

```
Stage 1  연습장          /Game/ThirdPerson/Lvl_ThirdPerson   (템플릿 맵, 코인 2개, 조작법 안내)
Stage 2  홍대 거리        /Game/Stages/Lvl_Hongdae
Stage 3  전주 경기전      /Game/Stages/Lvl_Gyeonggijeon
Stage 4  광화문 월대      /Game/Stages/Lvl_Gwanghwamun
Stage 5  제주 바닷가 포구  /Game/Stages/Lvl_JejuPier
→ 마지막 스테이지 뒤 전체 기록 요약, 12초 뒤 처음부터
```

## 0. 조작

| 키 | 동작 |
|---|---|
| W A S D / Space | 이동 / 점프 (공중에서 한 번 더: 이단 점프) |
| Space (턱 앞에서) | 기어오르기: 50cm~2.1m 높이의 턱 |
| Shift | 달리기 |
| C (또는 Ctrl) | 웅크리기 토글. 달리는 중이면 슬라이딩 |
| Q | 구르기 |
| R | 스테이지 재시작 |

달리기, 구르기, 슬라이딩으로 부딪히면 **부술 수 있는 장애물**(스캔의 행인, 간판, 노이즈 덩어리)이 부서집니다.
투명 벽은 3m 안으로 다가가면 하늘색 격자로 보입니다.

---

## 1. 폴더 구조

```
unreal_project/                 ← git 저장소 (코드만)
├─ HANDOFF.md, README.md
├─ Scans/                      ← ANNX 원본 (git 제외, 수정하지 않음)
│   └─ 0N_<Name>/<Name>.ply, <Name>_collision.glb, stage.json, README.md
├─ Build/                      ← 패키징된 게임 (git 제외)
└─ CoinDemo/                   ← 언리얼 프로젝트
    ├─ Source/CoinDemo/        게임 C++ (4장)
    ├─ Plugins/OpenSplat4D/    3DGS 렌더링 플러그인 (git 제외, 커밋 df76890)
    ├─ SourceAssets/           가져오기 전 원본 (git 제외)
    │   ├─ Quaternius/         애니메이션 팩 (CC0)
    │   ├─ CleanScans/         clean_scans.py가 만든 정리된 PLY
    │   └─ Sounds/             make_sounds.py가 합성한 효과음
    ├─ Scripts/                파이프라인 (3장)
    └─ Content/                언리얼 에셋 (git 제외)
        ├─ Stages/             스캔 스테이지 맵, 스플랫, 충돌, 방어막 재질
        ├─ MetaHumans/         주인공 MetaHuman
        ├─ Quaternius/         가져온 애니메이션, IK 리그, 리타게터
        └─ Audio/              효과음
```

에셋이 들어간 이전 저장소(2026-10-19 기준 스냅샷)는 `repository/unreal_project_assets_backup.git`에 로컬 백업으로 있습니다.

---

## 2. 개발 환경

### 엔진: 소스 빌드 (`C:\UE`, UE 5.8.3)
Epic 런처의 엔진 설치 버튼이 이 PC에서 계정과 상관없이 비활성화되어 있어서(원인 미확인) GitHub 소스로 빌드했습니다.

```bat
git clone --depth 1 -b release https://github.com/EpicGames/UnrealEngine.git C:\UE
C:\UE\Engine\Binaries\DotNET\GitDependencies\win-x64\GitDependencies.exe --force
C:\UE\GenerateProjectFiles.bat
C:\UE\Engine\Build\BatchFiles\Build.bat ShaderCompileWorker Win64 Development -WaitMutex
C:\UE\Engine\Build\BatchFiles\Build.bat UnrealVersionSelector Win64 Shipping -WaitMutex
C:\UE\Engine\Build\BatchFiles\Build.bat UnrealEditor Win64 Development -WaitMutex
C:\UE\Engine\Binaries\Win64\UnrealVersionSelector-Win64-Shipping.exe /register
```

### 이 PC에서 겪은 문제와 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| 에디터 빌드가 시작하자마자 실패 (`Could not find NetFxSDK`) | .NET Framework SDK 없음 | VS Installer → 개별 구성 요소 → .NET Framework 4.8 SDK, 4.6.2 대상 팩 |
| 빌드가 컴파일 1개씩만 돌아서 10시간 이상 예상 | 페이지 파일 5GB라 메모리 예약 한도 부족 → UBA가 병렬 수를 줄이거나 컴파일을 강제 종료 | 페이지 파일 64GB/96GB 고정 후 재부팅 → 22분 만에 완료 |
| WSL이 메모리 30GB를 잡고 있음 | WSL 기본 설정 | `sync; echo 3 > /proc/sys/vm/drop_caches` (필요하면 `.wslconfig`로 상한 설정) |
| `Visual C++ redistributable ... is outdated` | Setup.bat의 런타임 설치를 건너뜀 | `C:\UE\Engine\Extras\Redist\en-us\vc_redist.x64.exe` 실행 |
| Defender 때문에 빌드가 느림 | 실시간 검사 | `Add-MpPreference -ExclusionPath "C:\UE"` (관리자 PowerShell) |
| 외부 빌드 시 `Unable to build while Live Coding is active` | 에디터가 열려 있음 | 에디터를 닫고 빌드 |
| MetaHuman Creator 메뉴가 없음 | 플러그인 기본값이 꺼짐 | uproject에 `MetaHumanCharacter` 활성화 + 프로젝트 빌드(모듈 manifest 갱신) |

### 프로젝트 빌드 (에디터를 닫은 상태)
```bat
C:\UE\Engine\Build\BatchFiles\Build.bat CoinDemoEditor Win64 Development -Project=<repo>\CoinDemo\CoinDemo.uproject -WaitMutex
```

### 패키징 (에디터 없이 실행되는 exe)
```bat
C:\UE\Engine\Build\BatchFiles\RunUAT.bat BuildCookRun -project=<repo>\CoinDemo\CoinDemo.uproject -noP4 -platform=Win64 -clientconfig=Development -build -cook -stage -pak -archive -archivedirectory=<repo>\Build -utf8output -unattended -ignorecookerrors
```
결과: `Build/Windows/CoinDemo.exe` (약 4.8GB, 폴더째로 복사하면 다른 PC에서도 실행. DirectX 12 GPU 필요)
- 스테이지는 GameMode가 경로(soft reference)로 여는 맵이라 `DefaultGame.ini`의 `MapsToCook`에 등록되어 있어야 쿠킹에 포함됩니다.
- DX11(SM5)은 쿠킹 대상에서 뺐습니다. 3DGS 플러그인 셰이더가 SM5 한도(UAV 8개)를 넘어서 쿠커가 멈춥니다.
- `-ignorecookerrors`: 무해한 `LogUnrealNames: Error: String is too long` 한 줄 때문에 쿠킹이 실패 처리되는 것을 막습니다.

---

## 3. 파이프라인 (`CoinDemo/Scripts`)

에디터 밖에서 도는 스크립트(numpy, scipy, Pillow 필요)와 에디터 Python으로 도는 스크립트가 있습니다.

```bash
# 에디터 밖 (WSL)
uv venv /tmp/scanvenv && VIRTUAL_ENV=/tmp/scanvenv uv pip install numpy scipy pillow
```
```bat
:: 에디터 Python (에디터를 닫고)
C:\UE\Engine\Binaries\Win64\UnrealEditor-Cmd.exe <repo>\CoinDemo\CoinDemo.uproject -run=pythonscript -script=<repo>\CoinDemo\Scripts\<스크립트> -unattended -nopause -nosplash -stdout
```

| 순서 | 스크립트 | 어디서 | 하는 일 |
|---|---|---|---|
| 1 | `clean_scans.py` | 밖 | 스캔에서 줄무늬, 안개처럼 보이는 스플랫 제거 → `SourceAssets/CleanScans` |
| 2 | `make_scan_collision.py` | 밖 | 바닥, 벽, 부술 수 있는 장애물, 코인, 시작 방향 계산 → `generated/<Name>_collision.json/png` |
| 3 | `build_scan_stages.py` | 에디터 | 스플랫 가져오기 + LOD, 충돌 메시, 방어막 재질, 조명, 노출, 코인으로 스테이지 맵 생성 |
| - | `import_animations.py` | 에디터 | Quaternius 애니메이션 가져오기 + 마네킹으로 리타게팅 (처음 한 번) |
| - | `make_sounds.py` → `import_sounds.py` | 밖 → 에디터 | 효과음 합성, 가져오기 |
| - | `place_training_coins.py` | 에디터 | 1스테이지 코인 2개 배치 |
| - | `verify_scan_stages.py` | 에디터 | 스테이지 기본 검증 |

### 3-1. 좌표 변환 (가장 중요)
스캔 파일은 COLMAP 좌표계(-Y가 위, 오른손 좌표계, 임의 단위)이고 언리얼은 Z가 위, 왼손 좌표계, cm 단위입니다.
OpenSplat4D가 PLY를 가져올 때 `UE(X, Y, Z) = (z, x, -y) × 100`으로 변환합니다(`PLYFileReader.cpp:610`).
ANNX README의 공식과 같아서 **Splat Actor에는 회전 없이 균일 축척(metresPerUnit)만** 줍니다.
충돌, 코인, 시작점은 `make_scan_collision.py`가 같은 공식으로 직접 변환합니다.

### 3-2. 축척 보정 (`stage_scale.json`)
| 스테이지 | 보정 | 근거 |
|---|---|---|
| 홍대 | ×2.0 | 보정 전 걸을 수 있는 폭이 3~6m였는데, 실제로는 인도가 있는 2차선 도로 |
| 경기전 | ×1.0 | ANNX가 실측으로 맞춘 기준 스캔 |
| 광화문 | ×1.6 | 보정 전 난간 안쪽이 18×31m, 실제 월대는 29.7×48.7m |
| 제주 | ×1.6 | 실측 기준 없음. 광화문과 같은 방식으로 추정된 값이라 같은 보정 (**확인 필요**) |

### 3-3. 충돌과 장애물 (`make_scan_collision.py`)
- **바닥**: 0.5m 격자 높이맵으로 직접 만듭니다. ANNX glb 지면 메시는 구멍이 있어서 캐릭터가 빠졌습니다. 높이는 반경 2m 중앙값→평균 필터로 다듬어 출렁거림을 줄였습니다.
- **벽**: 칸마다 바닥 기준 0.5~2.5m 높이 스플랫의 **불투명도 합**이 10/㎡ 이상이면 벽입니다. 스캔은 반투명 스플랫이 겹쳐 면을 만들어서 개수가 아니라 불투명도 합으로 봅니다. 바닥이 없는 칸(가장자리)도 벽입니다.
- **부술 수 있는 장애물**: 맵 가장자리에 닿지 않는 6㎡ 미만의 벽 덩어리. 대부분 행인, 간판, 노이즈입니다.
- **코인 도달 검증**: 시작점에서 열린 칸(장애물은 열린 것으로 봄)을 따라 1.2m 이하 단차로 탐색합니다. 닿지 않는 코인은 가장 가까운 도달 가능 칸으로 옮깁니다.
- **시작 방향**: 카메라가 놓일 뒤쪽 공간이 가장 넓은 방향을 바라보게 합니다.
- 확인용 그림 `generated/<Name>_collision.png`: 회색 바닥, 빨강 벽, 주황 장애물, 노랑 코인, 파랑 시작점 (위쪽이 +X)

### 3-4. 렌더링에서 알아낸 것
- **Nanite 클러스터 LOD가 핵심입니다.** 가져오기만 하면 꺼져 있어서 2fps 수준이었습니다. `build_nanite_cluster_hierarchy()`로 켭니다.
- LOD 정밀도(0.03→0.005)는 화질 차이가 없었습니다. 건물 위쪽의 번짐은 스캔 원본의 한계입니다.
- **스캔 뒤에 아무것도 두지 않습니다.** 바닥과 벽이 희미한 스플랫의 겹침이라 뒤가 비칩니다. 안개를 넣으면 구멍이 하얗게, 색 바닥을 깔면 바닥 전체가 물들었습니다. 하늘 대기의 어두운 지면이 가장 잘 맞습니다.
- **스플랫은 노출(exposure)의 영향을 받지 않습니다.** 자동 노출이면 캐릭터 밝기만 시간에 따라 변해서, 스캔 스테이지는 수동 노출 +5.5 + 약한 조명(태양 0.8lux, 하늘 0.2)입니다.
- 광화문, 제주는 SH 3차, 홍대, 경기전은 원본이 1차입니다. 정렬은 매 프레임.
- 프로젝트 설정: FXAA, 모션 블러 끔 (스플랫은 모션 벡터가 없어서 TSR과 모션 블러가 번짐을 만듦).

### 3-5. 헤드리스(Commandlet) 실행 시 주의
- 플러그인의 `AGaussianSplatActor`는 `NotPlaceable` → 배치 가능한 래퍼 `AScanSplatActor` 사용.
- `spawn_actor_from_object`, 라인 트레이스는 헤드리스에서 동작하지 않습니다.
- 로드된 에셋은 `delete_asset`이 조용히 실패할 수 있습니다. 스플랫 재가져오기가 안 되면 `.uasset`을 직접 지우세요.

---

## 4. 게임 코드 (`CoinDemo/Source/CoinDemo`)

| 파일 | 역할 |
|---|---|
| `CoinDemoGameMode` | 스테이지 목록과 한글 이름, 코인 집계, 타이머, 최고 기록, 다음 스테이지, 재시작, 낙하 복귀, 방어막에 플레이어 위치 전달 |
| `CoinDemoCharacter` | 템플릿 캐릭터 + 런타임 입력(Shift, C, Q, R), 장애물 부수기(`MoveBlockedBy`), 카메라 각도 제한 |
| `CoinGame/TraversalComponent` | 달리기, 웅크리기, 슬라이딩, 구르기, 기어오르기, 이단 점프. 애니메이션은 DefaultSlot 동적 몽타주 |
| `CoinGame/CharacterAppearanceComponent` | MetaHuman을 스폰해서 숨긴 마네킹의 동작을 따라하게 함(Leader Pose). 카메라가 너무 가까우면 숨김 |
| `CoinGame/CoinPickup` | 코인: 회전, 둥실, 획득 시 소리와 튀어오르는 연출 |
| `CoinGame/BreakableBarrier` | 부술 수 있는 투명 장애물, 부서질 때 파편과 소리 |
| `CoinGame/CoinDemoHUD` | Canvas UI: 스테이지 패널, 타이머, 최고 기록, 타이틀 카드, 조작법, 클리어 배너, 전체 기록 |
| `CoinGame/CoinDemoSaveGame`, `CoinDemoGameInstance` | 스테이지별 최고 기록 저장, 한 판의 스테이지별 시간 |
| `CoinGame/ScanSplatActor` | OpenSplat4D 스플랫 컴포넌트를 담는 배치 가능한 Actor |
| `CoinGame/DevCapture` | 무인 테스트용: 명령줄로 스크린샷, 자동 플레이 봇, 시작 위치, 조명, 노출 조정 |

한글 문자열이 있는 `.cpp`는 UTF-8 BOM으로 저장해야 MSVC가 제대로 읽습니다.

### 애니메이션
- 템플릿 애니메이션 블루프린트(`ABP_Unarmed`)는 그대로 쓰고, 추가 동작은 `DefaultSlot`에 동적 몽타주로 얹습니다.
- 추가 동작은 [Quaternius Universal Animation Library 1, 2](https://quaternius.com/packs/universalanimationlibrary.html) (CC0). 척추 뼈 수가 달라서 IK 리그 자동 생성 + 리타게터로 마네킹에 옮겼습니다. 달리기(Sprint)는 리타게팅 결과가 어색해서 템플릿 달리기를 씁니다.
- 구르기와 기어오르기는 애니메이션 루트 모션으로 움직입니다. 기어오르기는 턱 높이에 맞춰 루트 모션 배율을 조절합니다.

### MetaHuman
`Content/MetaHumans/NewMetaHumanCharacter`. MetaHuman Creator에서 프리셋 → 오토 리깅(Epic 로그인) → 텍스처 다운로드 → 어셈블(Optimized, Medium).
몸 스켈레톤이 UE5 마네킹과 호환되어서 마네킹 애니메이션을 Leader Pose로 그대로 따라합니다.

---

## 5. 무인 테스트 (`DevCapture`)

```bat
UnrealEditor.exe <repo>\CoinDemo\CoinDemo.uproject /Game/Stages/Lvl_Hongdae -game -windowed -ResX=1600 -ResY=900 ^
  -StartAt=x,y,z,yaw -Bot=wait:3,DoSprintStart:0.1,coin:20 -ShotAt=5,10 -ShotYaw=30 -ShotPitch=-15 -ShotName=test -QuitAfterShots
```
- 봇 동작: `fwd/back/left/right[:초]`, `coin`(가까운 코인으로), `smash`(가까운 장애물로), `collectall`(치트), `jump`, `wait`, 캐릭터 함수 이름(`DoRoll`, `DoCrouch` 등)
- 스크린샷: `CoinDemo/Saved/Screenshots/<ShotName>_NN.png`
- 비교용: `-SplatLOD=`, `-SplatSH=`, `-LightScale=`, `-ExposureBias=`

---

## 6. 알려진 한계와 다음 할 일

- **제주 축척**은 추정값입니다. 실측 기준(방파제 폭 등)으로 확인이 필요합니다.
- **벽 감지는 근사치**입니다. 낮은 장애물은 통과되고 좁은 길이 막힐 수 있습니다(`WALL_OPACITY`, `BAND`, `MIN_WALL_AREA`, `BREAKABLE_MAX_AREA`).
- 광화문 성문의 흰 얼룩, 카메라 가까이의 큰 흐린 스플랫은 스캔 원본의 한계입니다. ANNX에 홍대, 경기전 SH 3차 원본을 요청하면 색 표현이 좋아집니다.
- 포복은 무료 애니메이션 팩에 없어서 슬라이딩으로 대체했습니다.
- 벽 근처에서는 카메라가 벽에 밀려 들어옵니다(캐릭터는 숨김 처리).
- OpenSplat4D는 신생 개인 저장소입니다(Apache-2.0). 엔진을 올리면 플러그인도 업데이트가 필요할 수 있습니다.
- 다음 후보: UMG로 HUD 다시 만들기, 메인 메뉴, 스테이지 시작 카메라 비행, 숨겨진 보석, 배경 음악.
