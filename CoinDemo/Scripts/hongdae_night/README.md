# 홍대 밤 거리 (`Lvl_Hongdae_Night`, 전부 CG)

이사님이 주차타워 PLY로 쓴 방식을 홍대 붉은 골목에 적용했습니다. 스캔은 화면에 쓰지 않고, 치수·배치·간판 종류의 원본으로만 씁니다.
- 바닥: 구역 A·B 재구성 메시
- 건물: 스캔이 잰 정면선과 높이, 정면 사진(`SourceAssets/Rebuilt/Hongdae/face_*.png`)을 보고 `bkit`으로 다시 지었습니다.

범위는 시작 교차로부터 붉은 골목 x 58m까지 양쪽 전부입니다. 거리 끝, 교차로 서쪽, 교차로 남북 방향은 건물로 막았습니다.

## 실행 순서
```bash
~/.venvs/gs/bin/python -I build_night.py          # 건물 메시, 간판, 재질, 조명, 코인 배치 → SourceAssets/Rebuilt/Hongdae_Night/
```
```bat
UnrealEditor-Cmd.exe CoinDemo.uproject -run=pythonscript -script=<repo>\CoinDemo\Scripts\hongdae_night\build_night_level.py
```
결과 화면은 `Saved/ScanQuality/Hongdae_Night/`에 있습니다.

## 구성
- **건물 26동**
  - 기준 건물 3동: SOLB, BIBIANG, BLUE ELEPHANT (`reimagined/hongdae_buildings.py`)
  - 나머지 23동: 템플릿 `street_building` 하나와 설정값으로 만듭니다(`night_buildings.py`).
- **템플릿이 만드는 것**
  - 1층 가게: 알루미늄 유리 전면, 내부 집기, 라이트박스 간판
  - 위층: 창문(일부만 불 켜짐, 블라인드), 층 간판, 에어컨, 돌출 간판, 채널 글자, 벽 광고
  - 측벽 창문, 파라펫, 옥상
- **간판 22종**: 실제 폰트로 그렸습니다. 예: Tax-Free, GOLDEN CREMA, 필름부착전문점, Coffee Brown, 닭갈비, 홍대 포차, 코인노래방, PC방, CU 편의점, medicube.
- **조명**
  - 가게마다 따뜻한 Rect Light(길로 새어 나오는 빛), 불 켜진 창 Rect Light, 간판 앞 색 Point Light: 그림자 끔
  - 가로등 Spot Light 7개(그림자 있음)
  - 낮은 달과 하늘 밝기를 올린 대기(남색 밤하늘), 볼륨 안개(불빛 번짐), 수동 노출 -4.3
- **젖은 도로**: 구역 A·B의 아스팔트와 붉은 포장, 노면 도색을 그대로 쓰되 어둡고 매끈하게 바꿨습니다. 큰 스케일 노이즈로 물웅덩이(거칠기 0.03)를 넣었습니다(`M_NightRoad_A/B`). x 46m 너머 길은 연장 메시입니다.
- **렌더링**: `RenderSettings` Actor가 레벨이 도는 동안 TSR과 Lumen 반투명 반사를 켭니다.
- **성능**: RTX 5080, 1600×900에서 80~120fps입니다. 셰이더 컴파일이 끝난 두 번째 실행부터 이 속도가 나옵니다.
- **게임**
  - 원래 홍대 스테이지의 코인과 코스는 교차로 서쪽(아직 CG가 없는 곳)에 있어서, 이 레벨에서는 지우고 다시 배치했습니다.
  - 붉은 골목을 따라 코인 14개가 있습니다.
  - Tax-Free 가게 옥상으로 가는 점프대가 있고, 옥상에 코인 1개와 숨겨진 보석이 있습니다.
  - 재구성 범위 밖은 투명 벽으로 막았습니다.

## 한계와 다음 후보
- 스테이지 목록에는 아직 넣지 않았습니다. 2스테이지 홍대를 이 레벨로 바꿀지는 정해야 합니다.
- 가게 내부는 단순합니다(흰 방과 기본 집기). 롯데 영상 같은 고급감을 내려면 차량, 사람, 데칼(얼룩, 전단지), 전선 다발, 더 다양한 간판이 필요합니다.
- 큰 측벽 일부는 아직 민짜 콘크리트입니다(광고판은 1곳만).
- 교차로 서쪽(원래 스테이지의 대부분)은 재구성하지 않았습니다.
