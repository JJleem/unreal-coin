# CoinDemo 핸드오프

언리얼 엔진 5.8로 만든 3인칭 코인 수집 데모입니다. 스테이지의 코인을 모두 모으면 다음 스테이지로 넘어가고,
2~5스테이지는 ANNX 3D 가우시안 스플래팅(3DGS) 실사 스캔을 그대로 맵으로 씁니다.

마지막 상태 (2026-10-19): 5개 스테이지 모두 플레이 가능, RTX 5080에서 120~300fps.

```
Stage 1  연습장          /Game/ThirdPerson/Lvl_ThirdPerson   (템플릿 맵, 코인 8개)
Stage 2  홍대 거리        /Game/Stages/Lvl_Hongdae
Stage 3  전주 경기전      /Game/Stages/Lvl_Gyeonggijeon
Stage 4  광화문 월대      /Game/Stages/Lvl_Gwanghwamun
Stage 5  제주 바닷가 포구  /Game/Stages/Lvl_JejuPier
```

---

## 1. 폴더 구조

```
unreal_project/
├─ HANDOFF.md                  ← 이 문서
├─ Scans/                      ← ANNX 쪽에서 전달받은 원본 (수정하지 않음)
│   ├─ STAGES.md               스테이지 선정 이유
│   └─ 0N_<Name>/
│       ├─ <Name>.ply          표준 3DGS PLY (원본 좌표계: -Y up, 스캔 단위)
│       ├─ <Name>_collision.glb 지면 높이 메시 (1 m 격자, 벽 없음)
│       ├─ stage.json          축척(metresPerUnit), 시작점, 코인 8개 좌표
│       └─ README.md
└─ CoinDemo/                   ← 언리얼 프로젝트
    ├─ Source/CoinDemo/        게임 C++ 코드 (아래 4장)
    ├─ Plugins/OpenSplat4D/    3DGS 렌더링 플러그인 (커밋 df76890 고정)
    ├─ Scripts/                스캔 → 스테이지 변환 파이프라인 (아래 3장)
    │   ├─ stage_scale.json    스테이지별 축척 보정값
    │   ├─ make_scan_collision.py
    │   ├─ build_scan_stages.py
    │   ├─ place_training_coins.py
    │   ├─ verify_scan_stages.py
    │   └─ generated/          make_scan_collision.py 결과물 (json + 확인용 png)
    └─ Content/Stages/         생성된 스테이지 맵과 에셋
```

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
| 빌드가 컴파일 1개씩만 돌아서 10시간 이상 예상 | 페이지 파일 5GB라 메모리 예약 한도 부족 → UBA가 병렬 수를 줄이거나 컴파일을 강제 종료 (`Low on memory ... Kill threshold`) | 페이지 파일 64GB/96GB 고정 후 재부팅 → 22분 만에 완료 |
| WSL이 메모리 30GB를 잡고 있음 | WSL 기본 설정 | `sync; echo 3 > /proc/sys/vm/drop_caches` (필요하면 `.wslconfig`로 상한 설정) |
| `Visual C++ redistributable ... is outdated` | Setup.bat의 런타임 설치를 건너뜀 | `C:\UE\Engine\Extras\Redist\en-us\vc_redist.x64.exe` 실행 |
| Defender 때문에 빌드가 느림 | 실시간 검사 | `Add-MpPreference -ExclusionPath "C:\UE"` (관리자 PowerShell) |
| 외부 빌드 시 `Unable to build while Live Coding is active` | 에디터가 열려 있음 | 에디터를 닫고 빌드 |

### 프로젝트 빌드
에디터를 닫은 상태에서 실행합니다.
```bat
C:\UE\Engine\Build\BatchFiles\Build.bat CoinDemoEditor Win64 Development -Project=<repo>\CoinDemo\CoinDemo.uproject -WaitMutex
```

---

## 3. PLY 스캔을 스테이지로 만드는 과정

```
Scans/0N_<Name>/            make_scan_collision.py         build_scan_stages.py
 <Name>.ply  ─────────────┬─────────────────────────────┬──→ Splat 에셋 + Nanite LOD
 <Name>_collision.glb ────┤  (WSL Python, numpy)        │
 stage.json ──────────────┘  generated/<Name>_          ├──→ 바닥 충돌 메시
 stage_scale.json ───────────  collision.json ──────────┼──→ 벽 충돌 메시
                                                        └──→ Lvl_<Name> 맵 (스캔, 충돌, 조명, 시작점, 코인)
```

### 3-1. 좌표 변환 (가장 중요)
스캔 파일은 COLMAP 좌표계(-Y가 위, 오른손 좌표계, 임의 단위)이고 언리얼은 Z가 위, 왼손 좌표계, cm 단위입니다.
OpenSplat4D가 PLY를 가져올 때 아래 공식으로 변환합니다(`Plugins/OpenSplat4D/Source/NanoGS/Private/PLYFileReader.cpp:610`).

```
UE(X, Y, Z) = (z, x, -y) × 100
```

ANNX README에 적힌 공식과 같아서 **Splat Actor에는 회전 없이 균일 축척(metresPerUnit)만** 주면 됩니다.
바닥, 벽, 코인, 시작점은 `make_scan_collision.py`가 같은 공식으로 직접 변환하므로 모두 정확히 겹칩니다.

### 3-2. 축척 보정 (`Scripts/stage_scale.json`)
ANNX가 준 `metresPerUnit`은 스플랫 크기로 추정한 값이라 오차가 큽니다(README 기준 ±20~30%, 실제로는 더 컸음).

| 스테이지 | 보정 | 근거 |
|---|---|---|
| 홍대 | ×2.0 | 보정 전 걸을 수 있는 폭이 3~6m였는데, 실제로는 인도가 있는 2차선 도로 |
| 경기전 | ×1.0 | ANNX가 실측으로 맞춘 기준 스캔 |
| 광화문 | ×1.6 | 보정 전 난간 안쪽이 18×31m, 실제 월대는 29.7×48.7m |
| 제주 | ×1.6 | 실측 기준 없음. 광화문과 같은 방식으로 추정된 값이라 같은 보정을 적용 (**확인 필요**) |

캐릭터가 크거나 작아 보이면 이 값만 바꾸고 아래 3-6의 명령을 다시 실행하면 됩니다.

### 3-3. 바닥 (`make_scan_collision.py`)
- `<Name>_collision.glb`(1m 격자 높이 메시)를 읽어서 언리얼 좌표로 변환합니다.
- 원본은 스캔 노이즈 때문에 1m마다 최대 28cm(p90)씩 들쭉날쭉해서 캐릭터가 출렁거렸습니다.
  → 반경 2m **중앙값 필터로 튀는 값을 제거한 뒤 평균 필터로** 다듬어서 12cm로 줄였습니다.
- 언리얼에서는 보이지 않는 StaticMesh로 만들고 `Use Complex As Simple` 충돌을 씁니다.

### 3-4. 벽 감지 (`make_scan_collision.py`)
glb에는 바닥만 있고 건물이나 벽이 없어서, 스플랫 분포로 장애물을 찾습니다.
1. 지도를 0.5m 격자로 나눕니다.
2. 칸마다 **바닥 기준 0.5~2.5m 높이(사람 키)에 있는 스플랫의 불투명도 합계**를 구합니다.
   - 이 스캔들은 반투명 스플랫 여러 개가 겹쳐서 면을 만듭니다(불투명도 중앙값이 약 0.06). 그래서 개수가 아니라 **불투명도 합**으로 판단합니다.
3. 합계가 10/㎡ 이상인 칸은 벽입니다. 기준값은 축척 보정의 제곱으로 나눠서, 축척을 바꿔도 같은 결과가 나오게 했습니다.
4. 1.5㎡보다 작은 덩어리(행인, 간판, 노이즈)는 제거합니다.
5. **바닥이 없는 칸(스캔 가장자리)도 벽**으로 처리해서 맵 밖으로 떨어지지 않게 합니다.
6. 코인과 시작점 주변 반경 1.5m는 항상 비워 둡니다.
7. 막힌 칸을 Y 방향으로 이어 붙여 박스로 만들고, 높이는 바닥 -1m ~ +4m입니다.

`generated/<Name>_collision.png`로 결과를 확인할 수 있습니다(회색: 걸을 수 있는 곳, 빨강: 벽, 노랑: 코인, 파랑: 시작점, 위쪽이 +X).

### 3-5. 렌더링 성능
- **Nanite 클러스터 LOD가 핵심입니다.** 가져오기만 하면 꺼져 있어서 469만 개 스플랫을 매 프레임 전부 그려 2fps 수준이었습니다.
  `build_scan_stages.py`가 `asset.build_nanite_cluster_hierarchy()`를 호출해서 켭니다(로그의 `path=NaniteCompaction nanite=1`로 확인 가능).
- 스플랫 SH 차수 1, 정렬은 매 프레임(2프레임마다로 하면 움직일 때 깜빡임).
- 프로젝트 설정: `r.AntiAliasingMethod=1`(FXAA), `r.DefaultFeature.MotionBlur=False`.
  스플랫은 모션 벡터가 없어서 TSR과 모션 블러가 움직일 때 번짐과 지글거림을 만듭니다.

### 3-6. 다시 만드는 방법
**1) 충돌 데이터 생성** (WSL, 언리얼 밖에서 실행. numpy, scipy, Pillow 필요)
```bash
uv venv /tmp/scanvenv && VIRTUAL_ENV=/tmp/scanvenv uv pip install numpy scipy pillow
cd CoinDemo/Scripts && /tmp/scanvenv/bin/python make_scan_collision.py
```

**2) 스테이지 맵 생성** (에디터를 닫고 Windows에서 실행. 스플랫 에셋과 LOD는 있으면 재사용)
```bat
C:\UE\Engine\Binaries\Win64\UnrealEditor-Cmd.exe <repo>\CoinDemo\CoinDemo.uproject -run=pythonscript -script=<repo>\CoinDemo\Scripts\build_scan_stages.py -unattended -nopause -nosplash -stdout
```

**3) (선택) 1스테이지 코인 재배치, 검증**: 같은 명령에서 스크립트만 `place_training_coins.py`, `verify_scan_stages.py`로 바꿔서 실행합니다.
`verify_scan_stages.py`는 바닥, 코인, 시작점, 스플랫을 확인하고 벽은 확인하지 않습니다.

### 3-7. 헤드리스(Commandlet) 실행 시 주의
- 플러그인의 `AGaussianSplatActor`는 `NotPlaceable`이라 스크립트로 배치할 수 없습니다.
  → 프로젝트에 배치 가능한 래퍼 `AScanSplatActor`를 만들어서 사용합니다.
- `spawn_actor_from_object`(에셋 드래그 방식)는 헤드리스에서 실패합니다. → `spawn_actor_from_class`를 사용합니다.
- 라인 트레이스가 아무것도 맞히지 않습니다. 그래서 1스테이지 코인은 블록 좌표를 보고 직접 정했습니다.

---

## 4. 게임 코드 (`CoinDemo/Source/CoinDemo`)

| 파일 | 역할 |
|---|---|
| `CoinGame/CoinPickup` | 코인. 기본 원기둥을 납작하게 만든 금색 메시. `Tick`에서 회전하고 위아래로 움직임. 플레이어가 닿으면 GameMode에 알리고 사라짐 |
| `CoinDemoGameMode` | 스테이지 목록과 한글 이름. 시작할 때 코인 수를 세고, 다 모으면 3초 뒤 다음 맵을 엶 (`BP_ThirdPersonGameMode`의 부모) |
| `CoinGame/CoinDemoHUD` | Canvas로 그리는 UI: 스테이지 번호와 이름, 코인 수, 진행 바, STAGE CLEAR 배너 |
| `CoinGame/ScanSplatActor` | OpenSplat4D 스플랫 컴포넌트를 담는 배치 가능한 Actor (충돌 없음) |
| `CoinDemoCharacter` | 템플릿 캐릭터 + `FellOutOfWorld` 재정의: Kill Z 아래로 떨어지면 시작점으로 순간이동 |

스테이지를 추가하려면 `CoinDemoGameMode.cpp` 생성자의 `StageList`에 맵 경로와 이름을 넣습니다.
한글 문자열이 있어서 이 파일은 UTF-8 BOM으로 저장해야 MSVC가 제대로 읽습니다.

---

## 5. 알려진 한계와 다음 할 일

- **제주 축척**은 추정값입니다. 실측 기준(방파제 폭 등)으로 확인이 필요합니다.
- **벽 감지는 근사치**입니다. 낮은 장애물(벤치, 화단)은 통과되고 좁은 길이 막힐 수 있습니다. `make_scan_collision.py`의 `WALL_OPACITY`, `BAND`, `MIN_WALL_AREA`로 조정합니다.
- 카메라 근처의 **큰 흐릿한 스플랫**은 3DGS 스캔 자체의 한계입니다.
- 스캔 에셋이 큽니다(홍대 약 340MB). git으로 관리하려면 Git LFS와 언리얼용 `.gitignore`가 필요합니다. 아직 git 저장소가 아닙니다.
- OpenSplat4D는 신생 개인 저장소입니다(Apache-2.0, 2026년 7월 생성). 5.8 이후 API 변경 경고가 있어서, 엔진을 올리면 플러그인도 업데이트해야 할 수 있습니다.
- 템플릿에는 웅크리기, 포복, 기어오르기 애니메이션이 없습니다(대시, 벽 점프, 이단 점프는 Platforming 변형에 있음).

---

## 6. 개선 계획 (2026-10-19 논의)

### 1단계: 바로 진행 (Claude)
| 작업 | 내용 |
|---|---|
| 캐릭터 그림자 | 투명 바닥 메시에 그림자만 받는 재질을 입혀서 캐릭터가 떠 보이지 않게 |
| 카메라 수정 | 벽 충돌이 Camera 채널을 무시하게 해서 투명 벽 근처에서 카메라가 튀지 않게 |
| 맵 화질 | 광화문, 제주의 SH를 3차로 복원 (렉 때문에 1차로 낮췄던 것), LOD 정밀도 상향 |
| 이동 능력 | Platforming 변형의 대시, 벽 점프, 이단 점프를 메인 캐릭터에 적용 |
| 투명 벽 표시 | 2m 이내로 다가가면 하늘색 격자 방어막이 보이고 멀어지면 사라짐 |
| 벽 부수기 | 대시로 부딪히면 두께 1m 이하의 얇은 벽만 부서짐 (파편, 화면 흔들림). 맵 경계와 건물은 유지 |
| git | 저장소 생성, Git LFS, 언리얼용 .gitignore |

### 2단계: 켜 두고 진행 (밤새, PC 절전 모드 끄기)
| 작업 | 내용 |
|---|---|
| 코인 도달 검증 | NavMesh로 시작점 → 모든 코인 경로 확인, 막힌 곳은 벽을 자동 조정 |
| 벽 감지 개선 | 잘못 감지된 벽(행인, 차, 간판)이 줄도록 기준을 보수적으로 |
| 노이즈 스플랫 정리 | 카메라 근처의 크고 흐릿한 떠 있는 조각 제거 |
| exe 패키징 | 에디터 없이 실행되는 데모 빌드 (게임팀 공유용) |

### 3단계: 사용자 작업 필요
| 작업 | 사용자 | Claude |
|---|---|---|
| 웅크리기, 포복, 기어오르기 | Mixamo에서 애니메이션 FBX 다운로드 (Adobe 계정) | 리타게팅, 이동 로직, 턱 잡고 올라가기(mantle) 구현 |
| 캐릭터 교체 | MetaHuman(엔진 내장) 또는 Mixamo 캐릭터 선택 | 연결, 애니메이션 리타게팅 |
| 스캔 원본 화질 | ANNX에 홍대, 경기전 SH 3차 원본 요청 | 다시 가져오기 |

### 그 밖의 후보
코인 효과음과 파티클, 스테이지 클리어 시간 기록, 스테이지 시작 카메라 비행 연출, UMG로 HUD 다시 만들기, 메인 메뉴.
