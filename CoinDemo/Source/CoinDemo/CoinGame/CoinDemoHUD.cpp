// Copyright Epic Games, Inc. All Rights Reserved.


#include "CoinDemoHUD.h"
#include "CoinDemoGameMode.h"
#include "CoinDemoGameInstance.h"
#include "CoinPickup.h"
#include "BreakableBarrier.h"
#include "GameMenuComponent.h"
#include "CanvasItem.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/SlateRenderer.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"

namespace CoinDemoHUD
{
	const FLinearColor Panel(0.02f, 0.02f, 0.04f, 0.55f);
	const FLinearColor Gold(1.0f, 0.75f, 0.1f);
	const FLinearColor Dim(1.0f, 1.0f, 1.0f, 0.6f);
	const FLinearColor BarBack(1.0f, 1.0f, 1.0f, 0.15f);
	const FLinearColor Record(0.45f, 1.0f, 0.55f);
	const FLinearColor Cyan(0.3f, 0.8f, 1.0f);
	const FLinearColor Gem(1.0f, 0.35f, 0.9f);

	/** 1:23.45 */
	FString FormatTime(float Seconds)
	{
		const int32 Minutes = FMath::FloorToInt(Seconds / 60.0f);
		return FString::Printf(TEXT("%d:%05.2f"), Minutes, Seconds - Minutes * 60.0f);
	}

	FLinearColor WithAlpha(const FLinearColor& Color, float Alpha)
	{
		return FLinearColor(Color.R, Color.G, Color.B, Color.A * Alpha);
	}
}

FString ACoinDemoHUD::MedalName(EStageMedal Medal)
{
	switch (Medal)
	{
	case EStageMedal::Gold: return TEXT("금메달");
	case EStageMedal::Silver: return TEXT("은메달");
	case EStageMedal::Bronze: return TEXT("동메달");
	default: return FString();
	}
}

FLinearColor ACoinDemoHUD::MedalColor(EStageMedal Medal)
{
	switch (Medal)
	{
	case EStageMedal::Gold: return FLinearColor(1.0f, 0.78f, 0.15f);
	case EStageMedal::Silver: return FLinearColor(0.8f, 0.85f, 0.95f);
	case EStageMedal::Bronze: return FLinearColor(0.9f, 0.5f, 0.25f);
	default: return FLinearColor::White;
	}
}

void ACoinDemoHUD::DrawHUD()
{
	Super::DrawHUD();

	const ACoinDemoGameMode* GM = GetWorld()->GetAuthGameMode<ACoinDemoGameMode>();
	if (!GM || !Canvas)
	{
		return;
	}

	// lay out for 1080p and scale to the actual resolution
	const float S = Canvas->ClipY / 1080.0f;
	MenuRects.Reset();

	const APlayerController* PC = GetOwningPlayerController();
	UGameMenuComponent* Menu = PC ? PC->FindComponentByClass<UGameMenuComponent>() : nullptr;

	if (GM->IsTitleScreen())
	{
		DrawLogo(S);
	}
	else
	{
		DrawStagePanel(GM, S);
		if (!GM->IsStageCleared())
		{
			DrawCompass(S);
			DrawPrompts(GM, S);
		}
		DrawTitleCard(GM, S);

		// the first stage teaches the controls
		if (GM->GetStageNumber() == 1 && !GM->IsStageCleared())
		{
			DrawTutorial(S, GM->GetTotalCoins());
		}

		DrawClear(GM, S);

		// hints, bottom right
		DrawShadowedText(TEXT("R 재시작   ·   ESC 일시정지"), CoinDemoHUD::Dim, Canvas->ClipX - 40.0f * S, Canvas->ClipY - 40.0f * S, 0.8f * S, FVector2D(1.0f, 1.0f));
	}

	if (Menu && Menu->GetMenu() != EGameMenu::None)
	{
		DrawMenu(Menu, S);
	}
}

void ACoinDemoHUD::DrawStagePanel(const ACoinDemoGameMode* GM, float S)
{
	using namespace CoinDemoHUD;

	const int32 Collected = GM->GetCollectedCoins();
	const int32 Total = GM->GetTotalCoins();

	const float PanelX = 40.0f * S, PanelY = 40.0f * S, PanelW = 420.0f * S, PanelH = 182.0f * S;
	DrawRect(Panel, PanelX, PanelY, PanelW, PanelH);
	DrawRect(Gold, PanelX, PanelY, 6.0f * S, PanelH);

	DrawShadowedText(FString::Printf(TEXT("STAGE %d / %d"), GM->GetStageNumber(), GM->GetStageCount()), Dim, PanelX + 30.0f * S, PanelY + 18.0f * S, 0.9f * S);
	DrawShadowedText(GM->GetStageName().ToString(), FLinearColor::White, PanelX + 30.0f * S, PanelY + 44.0f * S, 1.5f * S);

	// the coin counter pops briefly when a coin is collected
	const float SinceCoin = GetWorld()->GetTimeSeconds() - GM->GetLastCoinTime();
	const float Pop = SinceCoin < 0.35f ? 1.0f + 0.35f * FMath::Sin(SinceCoin / 0.35f * PI) : 1.0f;
	DrawShadowedText(FString::Printf(TEXT("COINS  %d / %d"), Collected, Total), Pop > 1.0f ? FLinearColor::White : Gold, PanelX + 30.0f * S, PanelY + 96.0f * S, 1.1f * S * Pop);

	// timer, top right of the panel
	const float Elapsed = GM->GetElapsedTime();
	DrawShadowedText(FormatTime(Elapsed), FLinearColor::White, PanelX + PanelW - 24.0f * S, PanelY + 18.0f * S, 1.0f * S, FVector2D(1.0f, 0.0f));

	// the next medal still in reach, and the best time
	EStageMedal Target = EStageMedal::None;
	for (const EStageMedal Medal : { EStageMedal::Gold, EStageMedal::Silver, EStageMedal::Bronze })
	{
		if (Elapsed <= GM->GetMedalTime(Medal))
		{
			Target = Medal;
			break;
		}
	}
	const float LineY = PanelY + 138.0f * S;
	if (GM->IsStageCleared() && GM->GetClearMedal() != EStageMedal::None)
	{
		DrawShadowedText(MedalName(GM->GetClearMedal()), MedalColor(GM->GetClearMedal()), PanelX + 30.0f * S, LineY, 0.85f * S);
	}
	else if (Target != EStageMedal::None)
	{
		DrawDiamond(PanelX + 38.0f * S, LineY + 10.0f * S, 11.0f * S, MedalColor(Target));
		DrawShadowedText(FString::Printf(TEXT("%s  %s"), *MedalName(Target), *FormatTime(GM->GetMedalTime(Target))), MedalColor(Target), PanelX + 54.0f * S, LineY, 0.85f * S);
	}
	else
	{
		DrawShadowedText(TEXT("메달 시간 초과"), Dim, PanelX + 30.0f * S, LineY, 0.85f * S);
	}

	const float Best = GM->GetPreviousBestTime();
	if (Best >= 0.0f)
	{
		DrawShadowedText(FString::Printf(TEXT("BEST %s"), *FormatTime(Best)), Dim, PanelX + PanelW - 24.0f * S, LineY, 0.85f * S, FVector2D(1.0f, 0.0f));
	}

	// hidden gem: a slot that lights up once found
	if (GM->HasGem())
	{
		const bool bFound = GM->GetGemTime() >= 0.0f || GM->WasGemFoundBefore();
		const float GemX = PanelX + PanelW - 34.0f * S, GemY = PanelY + 108.0f * S;
		DrawDiamond(GemX, GemY, 20.0f * S, bFound ? Gem : WithAlpha(FLinearColor::White, 0.18f));
		if (!bFound)
		{
			DrawShadowedText(TEXT("?"), Dim, GemX, GemY, 0.7f * S, FVector2D(0.5f, 0.5f));
		}
	}

	// coin progress bar along the bottom of the panel
	const float BarX = PanelX + 30.0f * S, BarY = PanelY + 126.0f * S, BarW = PanelW - 60.0f * S, BarH = 5.0f * S;
	DrawRect(BarBack, BarX, BarY, BarW, BarH);
	if (Total > 0)
	{
		DrawRect(Gold, BarX, BarY, BarW * Collected / Total, BarH);
	}

	DrawCombo(S, PanelX, PanelY + PanelH + 14.0f * S);
}

void ACoinDemoHUD::DrawTitleCard(const ACoinDemoGameMode* GM, float S)
{
	using namespace CoinDemoHUD;

	const float SinceStart = GetWorld()->GetTimeSeconds() - GM->GetStageStartTime();
	if (SinceStart >= 3.5f)
	{
		return;
	}

	const float In = FMath::Clamp(SinceStart / 0.4f, 0.0f, 1.0f);
	const float Out = FMath::Clamp((3.5f - SinceStart) / 0.8f, 0.0f, 1.0f);
	const float Alpha = FMath::Min(In, Out);
	const float CenterX = Canvas->ClipX * 0.5f, CenterY = Canvas->ClipY * 0.24f;
	DrawShadowedText(FString::Printf(TEXT("STAGE %d"), GM->GetStageNumber()), WithAlpha(Gold, Alpha), CenterX, CenterY - 40.0f * S, 1.3f * S, FVector2D(0.5f, 0.5f));
	DrawShadowedText(GM->GetStageName().ToString(), WithAlpha(FLinearColor::White, Alpha), CenterX, CenterY + 20.0f * S, 3.0f * S, FVector2D(0.5f, 0.5f));
	DrawShadowedText(FString::Printf(TEXT("코인 %d개를 모두 모으세요   ·   금메달 %s"), GM->GetTotalCoins(), *FormatTime(GM->GetMedalTime(EStageMedal::Gold))),
		WithAlpha(FLinearColor::White, 0.75f * Alpha), CenterX, CenterY + 90.0f * S, 1.0f * S, FVector2D(0.5f, 0.5f));
}

void ACoinDemoHUD::DrawPrompts(const ACoinDemoGameMode* GM, float S)
{
	using namespace CoinDemoHUD;

	const float CenterX = Canvas->ClipX * 0.5f;

	// gem found
	const float SinceGem = GetWorld()->GetTimeSeconds() - GM->GetGemTime();
	if (SinceGem < 3.0f)
	{
		const float Alpha = FMath::Min(FMath::Clamp(SinceGem / 0.3f, 0.0f, 1.0f), FMath::Clamp((3.0f - SinceGem) / 0.6f, 0.0f, 1.0f));
		DrawShadowedText(TEXT("숨겨진 보석 발견!"), WithAlpha(Gem, Alpha), CenterX, Canvas->ClipY * 0.3f, 2.2f * S, FVector2D(0.5f, 0.5f));
	}

	// close to a wall placed to be broken: say how
	const APawn* Player = GetOwningPawn();
	if (!Player)
	{
		return;
	}
	for (TActorIterator<ABreakableBarrier> It(GetWorld()); It; ++It)
	{
		if (It->IsAlwaysVisible() && It->GetBounds().ComputeSquaredDistanceToPoint(Player->GetActorLocation()) < FMath::Square(350.0f))
		{
			DrawShadowedText(TEXT("달리기 · 구르기 · 슬라이딩으로 부수기"), FLinearColor(1.0f, 0.6f, 0.25f), CenterX, Canvas->ClipY * 0.72f, 1.1f * S, FVector2D(0.5f, 0.5f));
			break;
		}
	}
}

void ACoinDemoHUD::DrawClear(const ACoinDemoGameMode* GM, float S)
{
	using namespace CoinDemoHUD;

	if (!GM->IsStageCleared())
	{
		return;
	}

	// stage clear banner, fading in over half a second
	const float Age = GetWorld()->GetTimeSeconds() - GM->GetStageClearedTime();
	const float Alpha = FMath::Clamp(Age / 0.5f, 0.0f, 1.0f);
	const float CenterX = Canvas->ClipX * 0.5f, CenterY = Canvas->ClipY * 0.4f;

	DrawRect(WithAlpha(Panel, Alpha), 0.0f, CenterY - 90.0f * S, Canvas->ClipX, 180.0f * S);

	const bool bLast = GM->IsLastStage();
	DrawShadowedText(bLast ? TEXT("ALL STAGES CLEAR!") : TEXT("STAGE CLEAR!"), WithAlpha(Gold, Alpha), CenterX, CenterY - 20.0f * S, 3.0f * S, FVector2D(0.5f, 0.5f));
	const bool bRecord = GM->IsNewRecord() && GM->GetPreviousBestTime() >= 0.0f;
	const FString Time = FString::Printf(TEXT("TIME %s"), *FormatTime(GM->GetElapsedTime()));
	const FString Line = bRecord
		? FString::Printf(TEXT("%s   NEW RECORD!"), *Time)
		: FString::Printf(TEXT("%s   %s"), *Time, bLast ? TEXT("Thanks for playing") : TEXT("Next stage..."));
	DrawShadowedText(Line, bRecord ? WithAlpha(Record, Alpha) : WithAlpha(FLinearColor::White, 0.8f * Alpha), CenterX, CenterY + 45.0f * S, 1.1f * S, FVector2D(0.5f, 0.5f));

	// the medal drops in a moment later
	const EStageMedal Medal = GM->GetClearMedal();
	if (Medal != EStageMedal::None && Age > 0.9f)
	{
		const float MedalAge = Age - 0.9f;
		const float Drop = FMath::Clamp(MedalAge / 0.25f, 0.0f, 1.0f);
		const float Size = FMath::Lerp(90.0f, 46.0f, Drop) * S;
		const float MedalX = CenterX + 470.0f * S, MedalY = CenterY;
		DrawDiamond(MedalX, MedalY, Size, WithAlpha(MedalColor(Medal), Drop));
		DrawShadowedText(MedalName(Medal), WithAlpha(MedalColor(Medal), Drop), MedalX, MedalY + 50.0f * S, 1.0f * S, FVector2D(0.5f, 0.0f));
		if (GM->IsNewMedal())
		{
			DrawShadowedText(TEXT("NEW"), WithAlpha(Record, Drop), MedalX, MedalY - 52.0f * S, 0.8f * S, FVector2D(0.5f, 1.0f));
		}
	}

	// after the last stage, the whole run
	const UCoinDemoGameInstance* Instance = GetGameInstance<UCoinDemoGameInstance>();
	if (bLast && Instance && Instance->GetResults().Num() > 0)
	{
		const TArray<FStageResult>& Results = Instance->GetResults();
		const float RowH = 34.0f * S, BoxW = 520.0f * S;
		const float BoxH = (Results.Num() + 2) * RowH + 30.0f * S;
		const float BoxX = CenterX - BoxW * 0.5f, BoxY = CenterY + 110.0f * S;
		DrawRect(WithAlpha(Panel, Alpha), BoxX, BoxY, BoxW, BoxH);

		float Y = BoxY + 15.0f * S;
		for (const FStageResult& Result : Results)
		{
			DrawShadowedText(Result.Name.ToString(), WithAlpha(FLinearColor::White, 0.85f * Alpha), BoxX + 30.0f * S, Y, 0.95f * S);
			DrawShadowedText(FormatTime(Result.Time), WithAlpha(FLinearColor::White, 0.85f * Alpha), BoxX + BoxW - 30.0f * S, Y, 0.95f * S, FVector2D(1.0f, 0.0f));
			Y += RowH;
		}
		Y += 10.0f * S;
		DrawRect(WithAlpha(Gold, 0.6f * Alpha), BoxX + 30.0f * S, Y - 6.0f * S, BoxW - 60.0f * S, 2.0f * S);
		DrawShadowedText(TEXT("TOTAL"), WithAlpha(Gold, Alpha), BoxX + 30.0f * S, Y, 1.1f * S);
		DrawShadowedText(FormatTime(Instance->GetTotalTime()), WithAlpha(Gold, Alpha), BoxX + BoxW - 30.0f * S, Y, 1.1f * S, FVector2D(1.0f, 0.0f));
	}
}

void ACoinDemoHUD::DrawLogo(float S)
{
	using namespace CoinDemoHUD;

	const float X = 120.0f * S, Y = Canvas->ClipY * 0.2f;
	const float Glow = 0.85f + 0.15f * FMath::Sin(GetWorld()->GetRealTimeSeconds() * 2.0f);
	DrawRect(WithAlpha(Gold, Glow), X, Y, 8.0f * S, 150.0f * S);
	DrawShadowedText(TEXT("COIN RUN"), WithAlpha(Gold, Glow), X + 36.0f * S, Y - 10.0f * S, 4.2f * S);
	DrawShadowedText(TEXT("스캔 도시 코인 레이스  ·  서울 · 전주 · 제주"), FLinearColor::White, X + 40.0f * S, Y + 112.0f * S, 1.1f * S);

	// progress across all stages
	const UCoinDemoSaveGame* SaveGame = UCoinDemoSaveGame::LoadOrCreate();
	int32 Golds = 0;
	for (const TPair<FString, EStageMedal>& Medal : SaveGame->BestMedals)
	{
		Golds += Medal.Value == EStageMedal::Gold ? 1 : 0;
	}
	DrawShadowedText(FString::Printf(TEXT("클리어 %d   ·   금메달 %d   ·   보석 %d"), SaveGame->BestTimes.Num(), Golds, SaveGame->Gems.Num()),
		Dim, X + 40.0f * S, Y + 160.0f * S, 0.9f * S);

	DrawShadowedText(TEXT("↑↓ 선택   ·   Enter 확인   ·   Esc 뒤로"), Dim, Canvas->ClipX - 40.0f * S, Canvas->ClipY - 40.0f * S, 0.8f * S, FVector2D(1.0f, 1.0f));
}

void ACoinDemoHUD::DrawMenu(UGameMenuComponent* Menu, float S)
{
	using namespace CoinDemoHUD;

	const bool bTitle = Menu->GetMenu() == EGameMenu::Title;
	if (!bTitle && !GetWorld()->GetAuthGameMode<ACoinDemoGameMode>()->IsTitleScreen())
	{
		// darken the paused game behind the menu
		DrawRect(FLinearColor(0.0f, 0.0f, 0.02f, 0.6f), 0.0f, 0.0f, Canvas->ClipX, Canvas->ClipY);
	}

	const TArray<FGameMenuItem> Items = Menu->GetItems();
	const bool bWide = Menu->GetMenu() == EGameMenu::StageSelect || Menu->GetMenu() == EGameMenu::Settings;
	const float RowH = (bWide ? 74.0f : 62.0f) * S;
	const float W = (bWide ? 760.0f : 440.0f) * S;
	const float X = bTitle ? 120.0f * S : (Canvas->ClipX - W) * 0.5f;
	float Y = bTitle ? Canvas->ClipY * 0.5f : (Canvas->ClipY - Items.Num() * RowH) * 0.5f;

	if (!bTitle)
	{
		DrawShadowedText(Menu->GetTitle(), Gold, X, Y - 70.0f * S, 1.8f * S);
	}

	// pick up the row under a moving mouse
	FVector2D Mouse(-1.0f, -1.0f);
	if (const APlayerController* PC = GetOwningPlayerController())
	{
		float MouseX, MouseY;
		if (PC->GetMousePosition(MouseX, MouseY))
		{
			Mouse = FVector2D(MouseX, MouseY);
		}
	}
	// a cursor resting where a menu opens (or jumping as the window appears) doesn't pick a row: hovering only
	// counts once the menu has been up for a moment
	const float Now = GetWorld()->GetRealTimeSeconds();
	if (Menu->GetMenu() != ShownMenu)
	{
		ShownMenu = Menu->GetMenu();
		MenuShownTime = Now;
	}
	const bool bMouseMoved = Now - MenuShownTime > 0.5f && LastMouse.X >= 0.0f && !Mouse.Equals(LastMouse, 1.0f);
	LastMouse = Mouse;

	for (int32 i = 0; i < Items.Num(); ++i)
	{
		const FGameMenuItem& Item = Items[i];
		MenuRects.Add(FVector4f(X, Y, W, RowH - 8.0f * S));
		if (bMouseMoved && Mouse.X >= X && Mouse.X <= X + W && Mouse.Y >= Y && Mouse.Y <= Y + RowH - 8.0f * S)
		{
			Menu->Select(i);
		}

		const bool bSelected = i == Menu->GetSelected();
		DrawRect(bSelected ? FLinearColor(0.16f, 0.11f, 0.01f, 0.85f) : FLinearColor(0.02f, 0.02f, 0.04f, 0.75f), X, Y, W, RowH - 8.0f * S);
		if (bSelected)
		{
			DrawRect(Gold, X, Y, 6.0f * S, RowH - 8.0f * S);
		}

		const FLinearColor TextColor = !Item.bEnabled ? WithAlpha(FLinearColor::White, 0.35f) : bSelected ? FLinearColor::White : FLinearColor(1.0f, 1.0f, 1.0f, 0.8f);
		const float TextY = Item.Detail.IsEmpty() ? Y + (RowH - 8.0f * S) * 0.5f : Y + 22.0f * S;
		DrawShadowedText(Item.Label, TextColor, X + 28.0f * S, TextY, 1.15f * S, FVector2D(0.0f, 0.5f));
		if (!Item.Value.IsEmpty())
		{
			DrawShadowedText(Item.Value, bSelected ? Gold : TextColor, X + W - 28.0f * S, TextY, 1.0f * S, FVector2D(1.0f, 0.5f));
		}
		if (!Item.Detail.IsEmpty())
		{
			DrawShadowedText(Item.Detail, WithAlpha(TextColor, 0.7f), X + 28.0f * S, Y + 48.0f * S, 0.75f * S, FVector2D(0.0f, 0.5f));
		}
		Y += RowH;
	}
}

int32 ACoinDemoHUD::GetMenuItemAtMouse() const
{
	for (int32 i = 0; i < MenuRects.Num(); ++i)
	{
		const FVector4f& R = MenuRects[i];
		if (LastMouse.X >= R.X && LastMouse.X <= R.X + R.Z && LastMouse.Y >= R.Y && LastMouse.Y <= R.Y + R.W)
		{
			return i;
		}
	}
	return INDEX_NONE;
}

void ACoinDemoHUD::DrawDiamond(float X, float Y, float Size, const FLinearColor& Color)
{
	FCanvasTileItem Tile(FVector2D(X - Size * 0.5f, Y - Size * 0.5f), Canvas->DefaultTexture->GetResource(), FVector2D(Size, Size), Color);
	Tile.Rotation = FRotator(0.0f, 45.0f, 0.0f);
	Tile.PivotPoint = FVector2D(0.5f, 0.5f);
	Tile.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Tile);
}

void ACoinDemoHUD::DrawCompass(float S)
{
	using namespace CoinDemoHUD;

	const APlayerController* PC = GetOwningPlayerController();
	const APawn* Player = PC ? PC->GetPawn() : nullptr;
	if (!PC || !Player || !PC->PlayerCameraManager)
	{
		return;
	}

	const FVector CameraLocation = PC->PlayerCameraManager->GetCameraLocation();
	const float CameraYaw = PC->PlayerCameraManager->GetCameraRotation().Yaw;

	// the bar covers 100 degrees either side of the view direction
	const float HalfAngle = 100.0f;
	const float CenterX = Canvas->ClipX * 0.5f, Y = 46.0f * S, HalfW = 330.0f * S;
	DrawRect(Panel, CenterX - HalfW, Y - 16.0f * S, HalfW * 2.0f, 32.0f * S);
	for (int32 i = -4; i <= 4; ++i)
	{
		const float TickX = CenterX + HalfW * i / 4.0f;
		DrawRect(i == 0 ? Gold : BarBack, TickX - 1.0f * S, Y + (i == 0 ? -16.0f : 8.0f) * S, 2.0f * S, 8.0f * S);
	}

	// every coin still waiting, the nearest one larger and with its distance
	const ACoinPickup* Nearest = nullptr;
	float NearestDistance = TNumericLimits<float>::Max();
	for (TActorIterator<ACoinPickup> It(GetWorld()); It; ++It)
	{
		if (It->GetActorEnableCollision())
		{
			const float Distance = FVector::Dist(It->GetActorLocation(), Player->GetActorLocation());
			if (Distance < NearestDistance)
			{
				Nearest = *It;
				NearestDistance = Distance;
			}
		}
	}

	for (TActorIterator<ACoinPickup> It(GetWorld()); It; ++It)
	{
		if (!It->GetActorEnableCollision())
		{
			continue;
		}
		const FVector ToCoin = It->GetActorLocation() - CameraLocation;
		const float Relative = FRotator::NormalizeAxis(ToCoin.Rotation().Yaw - CameraYaw);
		const bool bEdge = FMath::Abs(Relative) > HalfAngle;
		const float MarkerX = CenterX + HalfW * FMath::Clamp(Relative / HalfAngle, -1.0f, 1.0f);
		const bool bNearest = *It == Nearest;
		const float Size = (bNearest ? 15.0f : 10.0f) * S;
		DrawDiamond(MarkerX, Y, Size, bEdge ? FLinearColor(Gold.R, Gold.G, Gold.B, 0.5f) : Gold);

		if (bNearest)
		{
			// height difference matters on the scans: show whether to go up or down
			const float Rise = (It->GetActorLocation().Z - Player->GetActorLocation().Z) / 100.0f;
			const TCHAR* Arrow = Rise > 2.0f ? TEXT(" ↑") : Rise < -2.0f ? TEXT(" ↓") : TEXT("");
			DrawShadowedText(FString::Printf(TEXT("%dm%s"), FMath::RoundToInt(NearestDistance / 100.0f), Arrow), Gold, MarkerX, Y + 22.0f * S, 0.75f * S, FVector2D(0.5f, 0.0f));

			// and a marker over the coin itself while it is far away and in view
			FVector2D Screen;
			if (NearestDistance > 1200.0f && PC->ProjectWorldLocationToScreen(It->GetActorLocation() + FVector(0.0f, 0.0f, 60.0f), Screen))
			{
				const float Pulse = 0.7f + 0.3f * FMath::Sin(GetWorld()->GetRealTimeSeconds() * 5.0f);
				DrawDiamond(Screen.X, Screen.Y, 14.0f * S, FLinearColor(Gold.R, Gold.G, Gold.B, Pulse));
			}
		}
	}
}

void ACoinDemoHUD::DrawCombo(float S, float X, float Y)
{
	using namespace CoinDemoHUD;

	const ACoinDemoGameMode* GM = GetWorld()->GetAuthGameMode<ACoinDemoGameMode>();
	if (!GM || !GM->IsComboActive())
	{
		return;
	}

	// pops in with every coin, the bar shows the time left to keep the chain going
	const float SinceCoin = GetWorld()->GetTimeSeconds() - GM->GetLastCoinTime();
	const float Pop = SinceCoin < 0.3f ? 1.0f + 0.4f * FMath::Sin(SinceCoin / 0.3f * PI) : 1.0f;
	DrawShadowedText(FString::Printf(TEXT("COMBO x%d"), GM->GetCombo()), Gold, X + 30.0f * S, Y, 1.2f * S * Pop);
	if (GM->GetLastBonus() > 0.0f)
	{
		DrawShadowedText(FString::Printf(TEXT("-%.1fs"), GM->GetLastBonus()), Record, X + 250.0f * S, Y + 6.0f * S, 0.95f * S);
	}
	DrawRect(BarBack, X + 30.0f * S, Y + 44.0f * S, 200.0f * S, 4.0f * S);
	DrawRect(Gold, X + 30.0f * S, Y + 44.0f * S, 200.0f * S * GM->GetComboTimeLeft(), 4.0f * S);
}

void ACoinDemoHUD::DrawTutorial(float S, int32 CoinCount)
{
	using namespace CoinDemoHUD;

	struct FControl { const TCHAR* Key; const TCHAR* Action; };
	static const FControl Controls[] = {
		{ TEXT("W A S D"), TEXT("이동") },
		{ TEXT("Space"), TEXT("점프") },
		{ TEXT("Shift"), TEXT("달리기") },
		{ TEXT("C"), TEXT("웅크리기") },
		{ TEXT("Shift + C"), TEXT("슬라이딩 (달리면서)") },
		{ TEXT("Q"), TEXT("구르기") },
		{ TEXT("Space"), TEXT("기어오르기 (턱 앞에서)") },
		{ TEXT("초록 원판"), TEXT("점프대: 밟으면 높이 날아감") },
		{ TEXT("주황 벽"), TEXT("달리기 · 구르기로 부수기") },
		{ TEXT("◆ 보석"), TEXT("스테이지마다 하나씩 숨어 있음") },
	};

	const float RowH = 34.0f * S;
	const float PanelW = 460.0f * S, PanelH = 70.0f * S + RowH * UE_ARRAY_COUNT(Controls);
	const float PanelX = 40.0f * S, PanelY = Canvas->ClipY - PanelH - 40.0f * S;
	DrawRect(Panel, PanelX, PanelY, PanelW, PanelH);
	DrawRect(Gold, PanelX, PanelY, 6.0f * S, PanelH);

	DrawShadowedText(FString::Printf(TEXT("조작법  ·  코인 %d개를 모으세요"), CoinCount), Gold, PanelX + 30.0f * S, PanelY + 18.0f * S, 0.95f * S);

	float Y = PanelY + 56.0f * S;
	for (const FControl& Control : Controls)
	{
		DrawShadowedText(Control.Key, FLinearColor::White, PanelX + 30.0f * S, Y, 0.9f * S);
		DrawShadowedText(Control.Action, Dim, PanelX + 170.0f * S, Y, 0.9f * S);
		Y += RowH;
	}
}

void ACoinDemoHUD::DrawShadowedText(const FString& Text, const FLinearColor& Color, float X, float Y, float Scale, FVector2D Align)
{
	// a Slate font at the final size renders crisp at any scale, unlike scaling the canvas font
	const UFont* Font = GEngine->GetLargeFont();
	FSlateFontInfo FontInfo = Font->GetLegacySlateFontInfo();
	FontInfo.Size = FMath::Max(1.0f, Font->LegacyFontSize * Scale);

	const FVector2D Size = FSlateApplication::IsInitialized()
		? FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Text, FontInfo)
		: FVector2D::ZeroVector;
	X -= Size.X * Align.X;
	Y -= Size.Y * Align.Y;

	FCanvasTextItem Item(FVector2D(X, Y), FText::FromString(Text), FontInfo, Color);
	Item.EnableShadow(FLinearColor(0.0f, 0.0f, 0.0f, 0.6f * Color.A), FVector2D(FMath::Max(1.0f, 2.0f * Scale)));
	Canvas->DrawItem(Item);
}
