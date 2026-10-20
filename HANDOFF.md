# CoinDemo 핸드오프

언리얼 엔진 5.8로 만든 3인칭 코인 레이스 게임입니다. 스테이지의 코인을 모두 모으면 다음 스테이지로 넘어가고,
2~5스테이지는 ANNX 3D 가우시안 스플래팅(3DGS) 실사 스캔을 그대로 맵으로 씁니다. 주인공은 MetaHuman입니다.
스캔 위에는 **홀로그램 게임 레이어**(기둥 탑, 점프대, 떠 있는 발판, 부술 수 있는 주황 벽, 숨겨진 보석)가 얹혀 있어서
실제 장소 위에 AR 코스를 깐 것처럼 보이게 했습니다. 스캔과 억지로 섞지 않고 일부러 구분되는 스타일로 통일한 것입니다.

마지막 상태 (2026-10-20): 5개 스테이지 처음부터 끝까지 플레이 가능, RTX 5080에서 120~300fps.
코드 저장소: https://github.com/JJleem/unreal-coin (코드, 스크립트, 설정, 문서만. 에셋은 로컬)

```
타이틀     /Game/Stages/Lvl_Title   (광화문 스캔 복사본, 코인 없음, 카메라가 천천히 돎) → 처음부터 / 스테이지 선택 / 설정 / 종료
Stage 1  연습장          /Game/ThirdPerson/Lvl_ThirdPerson   (템플릿 맵, 코인 2개, 조작법 안내)
Stage 2  홍대 거리        /Game/Stages/Lvl_Hongdae
Stage 3  전주 경기전      /Game/Stages/Lvl_Gyeonggijeon
Stage 4  광화문 월대      /Game/Stages/Lvl_Gwanghwamun
Stage 5  제주 바닷가 포구  /Game/Stages/Lvl_JejuPier
→ 마지막 스테이지 뒤 전체 기록 요약, 12초 뒤 타이틀로
```

게임 요소
- **메달**: 스테이지마다 금, 은, 동 기준 시간. 시작점에서 코인을 가까운 순서로 도는 경로 길이로 자동 계산합니다(`ComputeMedalTimes`).
- **콤보**: 3초 안에 코인을 이어 먹으면 콤보. 콤보 한 단계마다 0.5초(최대 2초)를 기록에서 빼 줍니다. 코인 소리 음높이도 올라갑니다.
- **고스트**: 최고 기록을 세운 판의 움직임을 0.1초 간격으로 저장해서, 다음 판에 반투명 마네킹으로 함께 달립니다.
- **숨겨진 보석**: 스테이지마다 하나, 기둥 탑 꼭대기의 가운데 기둥 위. 기록에는 상관없고 세이브에 남습니다.
- **나침반**: 화면 위쪽 막대에 남은 코인 방향. 가장 가까운 코인은 거리와 높이 차(↑↓)를 표시합니다.
- **스테이지 잠금**: 이전 스테이지를 한 번 클리어해야 스테이지 선택에서 열립니다.
- 세이브: `CoinDemo/Saved/SaveGames/CoinDemo.sav` (최고 기록, 메달, 보석, 고스트, 설정). 지우면 처음 상태가 됩니다.

## 0. 조작

| 키 | 동작 |
|---|---|
| W A S D / Space | 이동 / 점프 (공중에서 한 번 더: 이단 점프) |
| Space (턱 앞에서) | 기어오르기: 50cm~2.1m 높이의 턱 |
| Shift | 달리기 |
| C (또는 Ctrl) | 웅크리기 토글. 달리는 중이면 슬라이딩 |
| Q | 구르기 |
| R | 스테이지 재시작 |
| ESC (또는 P, 패드 Start) | 일시정지 메뉴 / 메뉴에서 뒤로 |
| 메뉴 | ↑↓ 또는 W S, Enter 또는 Space, 마우스 클릭, 설정 값은 ← → |

설정: 마우스 감도, 상하 반전, 음량, 그래픽 품질, 전체 화면, 고스트 표시. 게임패드도 동작합니다.

달리기, 구르기, 슬라이딩으로 부딪히면 **부술 수 있는 장애물**이 부서집니다. 두 종류입니다.
- 주황 홀로그램 벽: 코스의 일부. 코인 하나를 가둔 우리 형태로 항상 보입니다.
- 투명 장애물: 스캔의 행인, 간판, 노이즈 덩어리. 투명 벽처럼 3m 안으로 다가가면 하늘색 격자로 보입니다.
초록 원판(점프대)을 밟으면 떠 있는 발판으로 날아갑니다. 비행 중에는 공중 감속을 꺼서 포물선이 끝까지 이어집니다.

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
| 1 | `clean_scans.py [Name]` | 밖 | 스캔에서 줄무늬, 안개, 떠 있는 조각 제거 → `SourceAssets/CleanScans`, 규칙별 개수 `generated/<Name>_clean.json`. v2 규칙은 `V2_STAGES`(현재 홍대만) |
| - | `reimport_stage_scan.py` | 에디터 | 정리본이 바뀐 스테이지의 스플랫 에셋을 같은 자리에 다시 가져오기(레벨은 그대로) |
| - | `import_test_splats.py` | 에디터 | `generated/import_jobs.json`의 PLY들을 `/Game/Stages/Tests/`에 비교용 에셋으로 가져오기. 게임에서 `-SplatAsset=`로 바꿔 봄 |
| - | `make_road_layer.py` → `build_road_layer.py` | 밖 → 에디터 | (실험, 미적용) 도로를 위에서 구운 정사영상 메시로 교체. 3-5절 참고 |
| 2 | `make_scan_collision.py` | 밖 | 바닥, 벽, 부술 수 있는 장애물, 코인, 시작 방향 계산 → `generated/<Name>_collision.json/png` |
| 0 | `make_materials.py` | 에디터 | 홀로그램, 발밑 그림자, 코인 재질 (`/Game/CoinGame/Materials`) |
| 3 | `build_scan_stages.py` | 에디터 | 스플랫 가져오기 + LOD, 충돌 메시, 방어막 재질, 조명, 노출, 코인, 홀로그램 코스로 스테이지 맵 생성 |
| 4 | `place_courses.py` | 에디터 | 이미 만든 스테이지의 코스만 다시 배치 (`plan_course` 수정 후 2번 → 이것) |
| 5 | `make_title_level.py` | 에디터 | 광화문 스테이지를 복사해 코인을 뺀 타이틀 맵 생성 (스테이지를 다시 만들면 다시 실행) |
| - | `import_animations.py` | 에디터 | Quaternius 애니메이션 가져오기 + 마네킹으로 리타게팅 (처음 한 번) |
| - | `make_sounds.py` → `import_sounds.py` | 밖 → 에디터 | 효과음 합성, 가져오기 |
| - | `place_training_coins.py` | 에디터 | 1스테이지 코인 2개 + 작은 연습 코스 배치 |
| - | `course_actors.py` | (모듈) | 코스 배치 공용 코드. 코스 Actor는 `Course_` 라벨로 찾아서 교체 |
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

### 3-4. 홀로그램 코스 (`plan_course` in `make_scan_collision.py`)
- 도달 가능한 칸 중 주변이 가장 넓게 트인 곳을 고릅니다(거리 변환). 시작점과 서로에게서 일정 거리 이상 떨어뜨립니다.
- **기둥 탑**: 땅에서 솟은 기둥 5개가 72°씩 돌며 1m씩 높아집니다. 3번째와 꼭대기에 코인, 가운데 기둥(+1.8m) 위에 보석.
  처음엔 떠 있는 얇은 판으로 만들었는데, 기어오르기가 벽면을 잡아야 해서 판 옆면(30cm)을 감지하지 못했습니다. 그래서 기둥입니다.
- **점프대**: 6m 위 3×3m 발판, 가장 트인 방향으로 5m. 발사 속도는 런타임에 중력으로 포물선을 풀어서 정확히 착지합니다(`AJumpPad`).
- **주황 우리**: 가장 트인 곳의 스캔 코인을 3.4m 사각 벽 4장으로 감쌉니다. 높이 3m라 이단 점프로도 못 넘습니다.
- 스캔마다 코인 3개(탑 2, 발판 1)가 늘어서 스캔 스테이지는 코인 11개입니다.
- 재질 `M_Hologram`: 면 테두리(UV), 50cm 월드 격자, 위로 흐르는 스캔 라인, 프레넬. `Color`, `Fill`, `Lines`, `Intensity` 파라미터.
  스캔 스테이지는 수동 노출 +5.5라 그대로면 하얗게 타서 밝기를 0.1배로 낮춥니다(`HoloStyle::GetIntensityScale`).
  고스트가 스켈레탈 메시라 `used_with_skeletal_mesh`가 켜져 있어야 합니다(꺼져 있으면 회색 기본 재질로 나옴).
- **발밑 그림자**: 스플랫은 그림자를 받지 않아서 캐릭터가 떠 보입니다. 바닥으로 트레이스해서 반투명 원판을 깝니다(스캔 스테이지만).

### 3-5. 렌더링에서 알아낸 것
- **Nanite 클러스터 LOD가 핵심입니다.** 가져오기만 하면 꺼져 있어서 2fps 수준이었습니다. `build_nanite_cluster_hierarchy()`로 켭니다.
- LOD 정밀도(0.03→0.005)는 화질 차이가 없었습니다. 건물 위쪽의 번짐은 스캔 원본의 한계입니다.
- **스캔 뒤에 아무것도 두지 않습니다.** 바닥과 벽이 희미한 스플랫의 겹침이라 뒤가 비칩니다. 안개를 넣으면 구멍이 하얗게, 색 바닥을 깔면 바닥 전체가 물들었습니다. 하늘 대기의 어두운 지면이 가장 잘 맞습니다.
- **스플랫은 노출(exposure)의 영향을 받지 않습니다.** 자동 노출이면 캐릭터 밝기만 시간에 따라 변해서, 스캔 스테이지는 수동 노출 +5.5 + 약한 조명(태양 0.8lux, 하늘 0.2)입니다.
- 광화문, 제주는 SH 3차, 홍대, 경기전은 원본이 1차입니다. 정렬은 매 프레임.
- 프로젝트 설정: FXAA, 모션 블러 끔 (스플랫은 모션 벡터가 없어서 TSR과 모션 블러가 번짐을 만듦).

### 3-6. 스캔 화질 분석과 정리 (2026-10-20, 홍대)
같은 카메라 6곳(`DevCapture -Views=`)에서 바꿔 가며 찍어 비교했습니다. 결과 이미지: `CoinDemo/Saved/ScanQuality/` (로컬).

원인별 결론
- **원본 데이터**: 홍대는 SH 1차(ANNX가 3차→1차로 줄임), 불투명도 중앙값 0.06(0.9 이상 0.1%)으로 도로·벽이 희미한 스플랫 여러 겹입니다. 학습 방식의 특성이라 전체 불투명도를 올려 덮지 않았습니다.
- **시점 외삽**: 건물 위쪽이 녹아내린 것처럼 보이는 것, 높은 곳(점프대 발판)에서 본 건물 뒤편의 번짐은 촬영하지 않은 각도라서 생깁니다. 어떤 필터로도 나아지지 않았습니다 → **재촬영(드론·높은 시점) 또는 재학습이 필요**.
- **렌더러(OpenSplat4D)**: 투영, 0.3px 저역 필터, 가우시안 감쇠, sRGB 블렌딩이 표준 3DGS와 같고 화면 해상도로 그립니다. `GaussianSharpness`는 셰이더에서 쓰이지 않습니다. `LODErrorThreshold`는 컬링에 그대로 쓰이고(0.1 하한은 캐시 비교용), `gs.DebugForceLODLevel 0`(최고 LOD 강제)도 차이가 없었습니다.
- **렌더 설정**: 렌더 해상도 150%는 작은 글자가 약간 선명하지만 FPS가 약 120→55로 절반, 톤매퍼 샤프닝·TSR·AA 끔은 차이가 미미해서 바꾸지 않았습니다.
- **정리 가능한 것**: 도로의 검은 긁힘(길쭉한 반투명 스플랫), 지붕 위 흰 조각(떠 있는 고립 스플랫).

적용한 정리 v2 (`clean_scans.py`): 기존 v1 + 길쭉한 반투명(길이비>15, 불투명도<0.4) + 작은 고립(8번째 이웃>0.3m이고 자기 크기의 3배 이상) + 하늘 조각(기둥별 상단 위의 고립). 4,689,666 → 4,390,703개(6.4% 제거, v1은 2.6%).
- 측정: 도로 어두운 긁힘 픽셀 시점별 5~9% 감소, 하늘 잡티 지표 16.4→16.0. FPS 같거나 약간 높음(교차 측정). 간판·계단·인도 디테일 손실 없음.
- 시도했다가 버린 것: 바닥 아래 스플랫 제거(도로에 검은 구멍), 크기 기준 제거(맨홀·균열·노면표시가 지워짐), 크기 무관 고립 제거(뒤의 어두운 층이 드러나 도로 얼룩), 높이 기준 하늘 제거(건물 위쪽 벽이 반투명해짐).
- **도로 정사영상 메시(미적용)**: 도로 스플랫을 위에서 앞→뒤로 합성해 텍스처를 굽고 바닥 높이맵 메시에 입혀 도로 스플랫을 대체(`Lvl_HongdaeHybrid`, 로컬). 긁힘은 60~70% 줄었지만, 촬영 경로 아래 위에서 안 보인 곳이 어두운 웅덩이처럼 보이고 먼 횡단보도가 뭉개지고 차·콘 밑동이 잘려 **원본보다 나빠서 적용하지 않았습니다**. 노출 보정 계수 0.022(수동 노출 +5.5 기준), 역 ACES로 스플랫과 밝기를 맞춤.
- 되돌리기: `clean_scans.py`의 `V2_STAGES`를 비우고 실행 → `reimport_stage_scan.py`. v1 정리본 사본: `SourceAssets/ScanTests/Hongdae_clean_v1.ply`.

### 3-7. 홍대 3D 재구성 (2026-10-20, 테스트 레벨)
`CoinDemo/Scripts/rebuild/` (README.md 참고). 실제 스테이지는 바꾸지 않았고 테스트 레벨 두 개를 만듭니다.
- `/Game/Stages/Lvl_Hongdae_Rebuilt`: 건물 메시 + 남은 스캔(하이브리드). `Lvl_Hongdae_RebuiltMesh`: 메시만(배경 없음, 도로 정사영상 메시).
- 도면: `Scripts/generated/Hongdae_plan.svg/png`. 주 도로 축(X)을 따라 1m마다 양쪽에서 '벽 모양' 스플랫(납작하고 수직, 지상 3~10m)이 처음 빽빽해지는 곳을 정면으로 잡고 계단식 직선으로 정리. 35개 정면 구간(181m) 중 24개를 건물로 만듦(11개는 벽이 거의 안 보이거나 나무여서 스캔 유지).
- 건물: 지붕 단계별 상자 44개. 높이는 정면 사진에서 '아래 2m가 대부분 벽인 가장 높은 줄'(측정), 깊이 8m와 평평한 지붕은 **추정**. 충돌 있음(코인·시작점·코스가 안에 들어가지 않게 깊이 조정). 그림자는 끔(스캔이 그림자를 못 받아 캐릭터만 그늘짐).
- 텍스처: 원본 사진·카메라 데이터가 없어(ANNX 스캔에 미포함, sky-clean-lab의 카메라 데이터는 다른 장면) 사진 투영은 불가. 각 면에 바깥에서 본 스플랫을 앞→뒤로 합성해 1.25cm/px로 구움(유리 너머 가게 안까지). 정면 89장, BC7, 언릿 + 역 ACES + 노출 보정 0.022로 스캔과 밝기 ±10% 이내.
- 하이브리드: 상자 안과 정면 바로 앞 스플랫 제거(439만→217만). FPS 스캔 v2 약 100~185 → 하이브리드 125~220 → 메시만 185~300(같은 6시점 교차 측정).
- 결과 판단: 정면 시점은 원본과 거의 같고, 건물 윤곽·모퉁이 벽이 단단해지고 정면 위 떠다니는 잡티가 사라짐. 대신 정면 텍스처가 원본보다 약간 흐리고, 유리의 하늘 반사(SH 시점 의존)가 사라지며, 사진이 없는 옆면·지붕은 단색. 멀리 녹아내린 건물 상단(시점 외삽)은 메시 텍스처에도 그대로 구워짐. 그래서 **실제 스테이지에는 아직 적용하지 않음**.
- 재실행: `rebuild/analyze_layout.py Hongdae` → `rebuild/build_geometry.py Hongdae`(약 3.5분) → 에디터 Python `rebuild\build_rebuilt_level.py`. 비교 이미지: `CoinDemo/Saved/ScanQuality/Rebuilt/`.

### 3-8. 헤드리스(Commandlet) 실행 시 주의
- 플러그인의 `AGaussianSplatActor`는 `NotPlaceable` → 배치 가능한 래퍼 `AScanSplatActor` 사용.
- `spawn_actor_from_object`, 라인 트레이스는 헤드리스에서 동작하지 않습니다.
- 로드된 에셋은 `delete_asset`이 조용히 실패할 수 있습니다. 스플랫 재가져오기가 안 되면 `.uasset`을 직접 지우세요.
- 맵 복사는 `duplicate_asset`이 두 번째부터 실패해서, 불러와 고친 뒤 `EditorLoadingAndSavingUtils.save_map(world, 새 경로)`로 다른 이름 저장합니다.
- `rerun_construction_scripts`는 C++ Actor에 없습니다. 크기 같은 값은 setter에서 바로 컴포넌트에 반영합니다.
- 재질 그래프에서 `Power` 노드 연결이 조용히 끊겨 결과가 0이 된 적이 있습니다. 곱하기로 대신합니다.

---

## 4. 게임 코드 (`CoinDemo/Source/CoinDemo`)

| 파일 | 역할 |
|---|---|
| `CoinDemoGameMode` | 스테이지 목록과 한글 이름, 코인 집계, 타이머, 콤보, 메달, 최고 기록과 고스트 저장, 보석, 다음 스테이지(페이드), 타이틀 카메라, 낙하 복귀, 방어막에 플레이어 위치 전달 |
| `CoinDemoPlayerController` | 템플릿 컨트롤러 + 메뉴 컴포넌트 |
| `CoinDemoCharacter` | 템플릿 캐릭터 + 런타임 입력(Shift, C, Q, R), 장애물 부수기(`MoveBlockedBy`), 카메라 각도 제한 |
| `CoinGame/TraversalComponent` | 달리기, 웅크리기, 슬라이딩, 구르기, 기어오르기, 이단 점프. 애니메이션은 DefaultSlot 동적 몽타주 |
| `CoinGame/CharacterAppearanceComponent` | MetaHuman을 스폰해서 숨긴 마네킹의 동작을 따라하게 함(Leader Pose). 카메라가 너무 가까우면 숨김 |
| `CoinGame/GameFeelComponent` | 손맛: 속도에 따른 시야각, 착지와 충돌 흔들림, 히트스톱, 발소리, 휙 소리, 발밑 그림자 |
| `CoinGame/GameMenuComponent` | 타이틀, 스테이지 선택, 설정, 일시정지 메뉴의 상태와 입력. 메뉴 키는 메뉴가 열려 있을 때만 별도 매핑 컨텍스트로 추가 |
| `CoinGame/CoinPickup` | 코인: 회전, 둥실, 3.2m 안이면 빨려옴, 콤보에 따라 소리 음높이 상승, 획득 연출 |
| `CoinGame/BreakableBarrier` | 부술 수 있는 장애물(투명 격자 또는 주황 홀로그램), 부서질 때 파편과 소리 |
| `CoinGame/HoloPlatform`, `JumpPad`, `GemPickup` | 홀로그램 발판/기둥, 포물선 점프대, 숨겨진 보석 |
| `CoinGame/GhostRunner` | 최고 기록 재생. 시뮬레이션 없이 기록된 속도만 이동 컴포넌트에 넣어 템플릿 애니메이션이 그대로 돌게 함 |
| `CoinGame/HoloStyle.h` | 스캔 스테이지에서 홀로그램 밝기 보정 |
| `CoinGame/CoinDemoHUD` | Canvas UI 전체: 스테이지 패널, 메달 목표, 보석 칸, 나침반, 콤보, 타이틀 카드, 조작법, 안내 문구, 클리어 배너와 메달, 전체 기록, 로고, 메뉴. 글자는 Slate 폰트를 최종 크기로 그려서 선명함 |
| `CoinGame/CoinDemoSaveGame`, `CoinDemoGameInstance` | 최고 기록, 메달, 보석, 고스트, 설정 저장(세션 동안 한 객체를 공유), 한 판의 스테이지별 시간 |
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
- 봇 동작: `fwd/back/left/right[:초]`, `coin`(가까운 코인으로), `smash`(가까운 장애물로), `collectall`(치트), `jump`, `wait`, 캐릭터 함수 이름(`DoRoll`, `DoCrouch` 등),
  메뉴 키 `MenuUp/MenuDown/MenuLeft/MenuRight/MenuConfirm/MenuBack` (타이틀처럼 캐릭터가 없어도 동작)
- 스크린샷 시간은 실제 시간 기준이라 일시정지 메뉴도 찍힙니다.
- 화질 비교: `-Views=x,y,z,yaw,pitch;...`(시점마다 3초), `-NoHUD`, `-HidePlayer`, `-Cvars=r.ScreenPercentage=150;...`, `-SplatAsset=/Game/Stages/Tests/...`, `-SplatOpacity=`, `-SplatScale=`. 스크린샷마다 직전 구간 평균 FPS가 로그에 남습니다.
- WSL에서 `/mnt/c`의 큰 PLY를 `np.fromfile`로 읽으면 가끔 덜 읽힙니다. 스크립트는 한 번에 읽고 길이를 확인합니다.
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
- 메달 기준 시간은 경로 길이로 자동 계산한 값이라 스테이지에 따라 쉽거나 어려울 수 있습니다. 직접 플레이해 보고 `ComputeMedalTimes`의 계수를 조정하세요.
- 코스 위치는 자동 선택이라 탑이 맵 가장자리(홍대)나 시작점 근처(경기전)에 놓이기도 합니다. 마음에 안 들면 `plan_course`에서 좌표를 고정할 수 있습니다.
- 고스트는 템플릿 마네킹 + 기본 이동 애니메이션이라 구르기, 기어오르기 동작은 재생하지 않습니다(위치는 따라감).
- 배경 음악과 환경음은 넣지 않았습니다(요청에 따라 제외).
- 다음 후보: 움직이는 발판(`AHoloPlatform::SetMovement`는 이미 있음), 스테이지 시작 카메라 비행, 온라인 순위표.
