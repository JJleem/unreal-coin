# 주차타워 스테이지 (`Lvl_ParkingTower`, 6스테이지)

감독 영상의 주차타워 PLY(`parking-tower/scene.compressed (2).ply`)로 만든 스테이지입니다.
역분석(`../parkingtower/README.md`) 결론대로 **원본 PLY를 정리 없이 그대로** 쓰고, 렌더링은 그때 가장 좋았던 설정(TSR + `gs.ToneCorrection 1`)입니다.
같은 화면 기준으로 감독 영상과의 색 오차가 0.03 수준입니다. RTX 5080, 1600×900에서 130~150fps입니다.

## 실행 순서

```bash
# 에디터 밖 (WSL, ~/.venvs/gs: numpy, scipy, Pillow, torch)
~/.venvs/gs/bin/python -I survey.py     # 배치(수평·방향) 측정 + 지도
~/.venvs/gs/bin/python -I ortho.py      # 위에서 본 정사영상 (CUDA), 아래 그림들의 배경
~/.venvs/gs/bin/python -I objects.py    # 바닥 높이장, 기둥·차·난간 같은 고체
~/.venvs/gs/bin/python -I plan.py       # 플레이 영역, 충돌 상자, 코스 → generated/ParkingTower_stage.json, plan.png
```
```bat
:: 에디터 Python (에디터를 닫고)
UnrealEditor-Cmd.exe <repo>\CoinDemo\CoinDemo.uproject -run=pythonscript -script=<repo>\CoinDemo\Scripts\parkingstage\build_parking_stage.py
```
입력은 역분석 때 해제한 `SourceAssets/ParkingTower/ParkingTower_raw.ply`와, 그 PLY를 가져온 에셋 `/Game/Stages/ParkingTower/PT_Raw`(클러스터 LOD 포함)입니다.
중간 결과는 `SourceAssets/ParkingStage/`(git 제외)에 저장합니다.
- `placement.json`
- `survey_*.png`
- `ortho_low.png`: 2.1m 아래 스플랫만 위에서 표준 3DGS로 그린 정사영상(5cm/px)
- `objects.json/png`
- `plan.png`

## 배치 (`survey.py`, `ptstage.py`)
- 주황 기둥 피복 16개를 찾아 기둥 열 방향을 구했습니다(-3.95°). 이 방향을 언리얼 X축으로 돌립니다.
- 바닥 평면(잔차 3.4cm)의 기울기 0.64°는 pitch 0.61°, roll -0.18°로 바로잡습니다.
- 덱 중앙이 원점, 바닥이 Z=0이 되게 위치를 정합니다. 축척은 3.846 m/단위(주차칸 폭 2.5m 기준)입니다.
- Splat Actor에 그대로 넣습니다: `world = R(rotator) · (local × MPU) + location`.
  - 레벨 빌드 때 언리얼 Transform과 같은지 검사합니다. 오차는 0.00cm였습니다.
  - `ptstage.rotation_matrix`는 언리얼 `FRotationMatrix`와 같은 식입니다.

## 충돌 (`objects.py`, `plan.py`)
- **바닥**: 50cm 격자의 높이장입니다. 바닥 근처 스플랫 높이의 최빈값에 중앙값 필터를 적용했습니다. 덱은 끝에서 끝까지 ±15cm 오르내립니다.
- **고체**: 바닥 위 30~190cm 스플랫의 불투명도 합이 120/㎡ 이상인 10cm 칸입니다.
  - 기둥 21개, 차 4대, 양쪽 난간, 섬 끝 막이, 안쪽 주차칸 볼라드, 끝벽이 잡힙니다(`objects.png`).
  - 0.1㎡ 미만 덩어리는 잡티로 보고 뺐습니다.
  - 스캔에 보이는 물체라서 숨긴 충돌로 둡니다. 높이는 천장까지입니다.
- **경계**: 플레이 영역 밖이면서 고체가 없는 곳, 즉 경사로 입구와 로비 쪽만 다른 스테이지와 같은 하늘색 격자 벽(`M_Barrier`)입니다.
- **천장**: 바닥 위 335cm에 판을 둡니다(슬래브 아래 331cm). 점프와 카메라가 천장 위로 나가지 않게 막습니다.
- **플레이 영역** (`DECK_ADD`, `DECK_CUT`)
  - 포함: 양쪽 통로, 주차열, 가운데 섬, 끝의 볼라드 주차칸
  - 제외: 경사로(+X 끝, 높이가 ±50cm 변함), 왼쪽 아래 밝은 로비, 왼쪽 위 벽
  - 영역 밖은 촬영 경로를 벗어나 번진 곳입니다.

## 코스 (천장이 3.3m라 높이 대신 달리기 위주)
다른 스테이지의 기둥 탑(6.8m)과 6m 점프대는 들어가지 않습니다. 캐릭터 키가 1.92m라 1.1m보다 높은 곳에 서면 머리가 천장에 닿습니다.
그래서 감독 영상의 AR 오버레이(빈자리 초록 상자, 경로 화살표) 스타일로 코스를 만들었습니다.
- **코인 13개 + 보석**
  - 진행 순서: 시작(앞쪽 교차 통로) → 왼쪽 통로 → 끝 교차 통로와 볼라드 주차칸 → 오른쪽 통로 → 점프대로 섬을 넘어 시작 쪽
  - 모든 코인에 시작점에서 걸어서 닿을 수 있는지 격자 탐색으로 확인했습니다.
- **AR 주차칸**: 빈 주차칸 4곳(왼쪽 열 2곳, 섬 1곳, 앞쪽 EV 칸 1곳)에 코인이 있습니다.
  - 칸마다 바닥에 얇은 초록 윤곽선을 긋고, HUD가 "주차 가능" 라벨을 띄웁니다(`AARLabel`). 라벨은 코인을 먹으면 사라집니다.
- **차단기 4개** (빨간 바, 바닥 위 135~160cm, 흰 기둥)
  - 걸어서는 지나갈 수 없습니다(캡슐 192cm). 천장 때문에 이단 점프로 넘을 수도 없습니다.
  - **달리다 슬라이딩**(웅크린 캡슐 120cm)으로 밑을 지나갑니다. 차단기 2개 밑에 코인이 있습니다.
- **점프대**: 오른쪽 통로 끝에서 섬을 넘어 왼쪽 통로로 날아갑니다(`arc_height` 90cm). 포물선 꼭대기(바닥 위 2m)에 코인이 있습니다. 빛기둥은 천장 아래로 줄였습니다.
- **주황 철창**: 왼쪽 열의 빈칸 하나를 감쌉니다. 달리기, 구르기, 슬라이딩으로 부숩니다.
- **낮은 발판**: 끝 교차 통로에 40·80·110cm 계단이 있고 꼭대기에 코인이 있습니다. 보석은 왼쪽 위 장애인 주차칸 구석의 90cm 발판 위입니다.
- **경로선**: 진행 순서를 따라 바닥에 30cm 폭의 하늘색 선을 그었습니다.
  - 모서리는 둥글게 처리했고, 1.6m마다 갈매기표가 있습니다. 감독 영상의 내비게이션 선과 같은 형식입니다.
  - 정점으로 만든 메시 3개(경로, 갈매기표, 주차칸)입니다.
- 차단기에는 빨간 "슬라이딩" 라벨이 붙습니다(15m 안에서만 보임).

### AR 표시 재질과 카메라 (1차 결과가 "구리다"는 피드백 뒤 바꾼 것)
감독 영상과 같은 카메라로 찍은 언리얼 화면은 영상과 거의 같았습니다(`../parkingtower` 비교). 차이는 그 위에 얹은 것에서 나왔습니다.
1. 기존 홀로그램 재질(격자, 스캔라인)로 만든 커다란 반투명 상자가 게임처럼 보였습니다.
2. 3인칭 카메라가 2.5m 높이, 90° 이상 화각으로 내려다봤습니다.

그래서 이 스테이지만 다음처럼 바꿨습니다.
- **재질**: `M_ARGlow`(면 테두리만 밝고 채움은 옅은 무광 발광, 격자·스캔라인 없음, 발판·차단기·철창)와 `M_AR_Route/Chevron/Stall`(바닥 선)
  - 고정 노출 +5.5(×45) 때문에 발광값은 0.03 수준으로 아주 작게 줍니다.
- **코인 색**: 기본 금색이 하얗게 날아가서 (0.42, 0.26, 0.02)로 낮췄습니다.
- **카메라** `AStageView`: 화각 65°(달릴 때 +5°), 붐 430cm, 어깨 너머 오프셋(0, 60, 35), 시선 -35°~+12°. 다른 스테이지는 그대로입니다.

## 조명·렌더링
- 스플랫은 원본 그대로 SH 3차이고 매 프레임 정렬합니다.
- `BeforeAfterDemo` Actor(`RenderSettings`)가 레벨이 도는 동안만 TSR과 `gs.ToneCorrection 1`을 켭니다. `demo_controls`를 꺼서 B 키와 안내 문구는 없습니다.
  - 이동 중 프레임도 비교했는데, TSR이 FXAA보다 선명하고 잔상이 없었습니다.
- 캐릭터 조명: 천장 조명처럼 위에서 오는(-72°) 차가운 흰색 태양과 하늘빛입니다. 스캔 스테이지 값에 톤 보정 이득 1.64를 곱했고, 노출은 고정 +5.5입니다.

## 함께 바꾼 코드
- `HoloPlatform`: `Fill`, `Brightness`, `bSolid`(false면 충돌 없는 표시용)
- `StageView.h/.cpp` (새 파일)
  - `AStageView`: 스테이지별 카메라. `GameFeelComponent`가 화각과 붐, 캐릭터가 시선 범위에 적용합니다.
  - `AARLabel`: HUD가 월드 위치에 그리는 라벨. 거리에 따라 흐려지고 가려지면 숨습니다(`CoinDemoHUD::DrawWorldLabels`).
- `CoinPickup`: 자석(3.2m)이 **시야가 트였을 때만** 끌어옵니다. 벽 너머나 부수기 전의 철창 안 코인이 빨려 나오지 않습니다. 모든 스테이지에 적용됩니다.
- `BeforeAfterDemo`: `bDemoControls`
- `CoinDemoGameMode`: 스테이지 목록에 6번 추가, `MarkCheated`
  - DevCapture `collectall`로 끝낸 판은 기록, 메달, 고스트를 저장하지 않습니다.
- `DevCapture`: `-ForgetStage=Lvl_이름`은 세이브에서 그 스테이지의 기록, 메달, 고스트, 보석을 지웁니다.
- `DefaultGame.ini` `MapsToCook`에 추가, `build_scan_stages.py`의 `main()`을 `__main__`일 때만 실행하게 함(이 빌더가 헬퍼를 import)
