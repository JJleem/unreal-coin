// Copyright Epic Games, Inc. All Rights Reserved.


#include "CoinDemoHUD.h"
#include "CoinDemoGameMode.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/World.h"
#include "CoinDemoGameInstance.h"

namespace CoinDemoHUD
{
	const FLinearColor Panel(0.02f, 0.02f, 0.04f, 0.55f);
	const FLinearColor Gold(1.0f, 0.75f, 0.1f);
	const FLinearColor Dim(1.0f, 1.0f, 1.0f, 0.6f);
	const FLinearColor BarBack(1.0f, 1.0f, 1.0f, 0.15f);
	const FLinearColor Record(0.45f, 1.0f, 0.55f);

	/** 1:23.45 */
	FString FormatTime(float Seconds)
	{
		const int32 Minutes = FMath::FloorToInt(Seconds / 60.0f);
		return FString::Printf(TEXT("%d:%05.2f"), Minutes, Seconds - Minutes * 60.0f);
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

	using namespace CoinDemoHUD;

	// lay out for 1080p and scale to the actual resolution
	const float S = Canvas->ClipY / 1080.0f;
	const int32 Collected = GM->GetCollectedCoins();
	const int32 Total = GM->GetTotalCoins();

	// stage panel, top left
	const float PanelX = 40.0f * S, PanelY = 40.0f * S, PanelW = 420.0f * S, PanelH = 150.0f * S;
	DrawRect(Panel, PanelX, PanelY, PanelW, PanelH);
	DrawRect(Gold, PanelX, PanelY, 6.0f * S, PanelH);

	DrawShadowedText(FString::Printf(TEXT("STAGE %d / %d"), GM->GetStageNumber(), GM->GetStageCount()), Dim, PanelX + 30.0f * S, PanelY + 18.0f * S, 0.9f * S);
	DrawShadowedText(GM->GetStageName().ToString(), FLinearColor::White, PanelX + 30.0f * S, PanelY + 44.0f * S, 1.5f * S);
	// the coin counter pops briefly when a coin is collected
	const float SinceCoin = GetWorld()->GetTimeSeconds() - GM->GetLastCoinTime();
	const float Pop = SinceCoin < 0.35f ? 1.0f + 0.35f * FMath::Sin(SinceCoin / 0.35f * PI) : 1.0f;
	DrawShadowedText(FString::Printf(TEXT("COINS  %d / %d"), Collected, Total), Pop > 1.0f ? FLinearColor::White : Gold, PanelX + 30.0f * S, PanelY + 96.0f * S, 1.1f * S * Pop);

	// stage timer and best time, top right of the panel
	const float Best = GM->GetPreviousBestTime();
	DrawShadowedText(FormatTime(GM->GetElapsedTime()), FLinearColor::White, PanelX + PanelW - 24.0f * S, PanelY + 18.0f * S, 1.0f * S, FVector2D(1.0f, 0.0f));
	if (Best >= 0.0f)
	{
		DrawShadowedText(FString::Printf(TEXT("BEST %s"), *FormatTime(Best)), Dim, PanelX + PanelW - 24.0f * S, PanelY + 100.0f * S, 0.8f * S, FVector2D(1.0f, 0.0f));
	}

	// coin progress bar along the bottom of the panel
	const float BarX = PanelX + 30.0f * S, BarY = PanelY + PanelH - 14.0f * S, BarW = PanelW - 60.0f * S, BarH = 5.0f * S;
	DrawRect(BarBack, BarX, BarY, BarW, BarH);
	if (Total > 0)
	{
		DrawRect(Gold, BarX, BarY, BarW * Collected / Total, BarH);
	}

	// restart hint, bottom right
	DrawShadowedText(TEXT("R  재시작"), Dim, Canvas->ClipX - 40.0f * S, Canvas->ClipY - 40.0f * S, 0.8f * S, FVector2D(1.0f, 1.0f));

	// stage title card for the first seconds
	const float SinceStart = GetWorld()->GetTimeSeconds() - GM->GetStageStartTime();
	if (SinceStart < 3.5f)
	{
		const float In = FMath::Clamp(SinceStart / 0.4f, 0.0f, 1.0f);
		const float Out = FMath::Clamp((3.5f - SinceStart) / 0.8f, 0.0f, 1.0f);
		const float Alpha = FMath::Min(In, Out);
		const float CenterX = Canvas->ClipX * 0.5f, CenterY = Canvas->ClipY * 0.2f;
		DrawShadowedText(FString::Printf(TEXT("STAGE %d"), GM->GetStageNumber()), FLinearColor(Gold.R, Gold.G, Gold.B, Alpha), CenterX, CenterY - 40.0f * S, 1.3f * S, FVector2D(0.5f, 0.5f));
		DrawShadowedText(GM->GetStageName().ToString(), FLinearColor(1.0f, 1.0f, 1.0f, Alpha), CenterX, CenterY + 20.0f * S, 3.0f * S, FVector2D(0.5f, 0.5f));
		DrawShadowedText(FString::Printf(TEXT("코인 %d개를 모두 모으세요"), Total), FLinearColor(1.0f, 1.0f, 1.0f, 0.75f * Alpha), CenterX, CenterY + 90.0f * S, 1.0f * S, FVector2D(0.5f, 0.5f));
	}

	// the first stage teaches the controls
	if (GM->GetStageNumber() == 1 && !GM->IsStageCleared())
	{
		DrawTutorial(S, Total);
	}

	// stage clear banner, fading in over half a second
	if (GM->IsStageCleared())
	{
		const float Age = GetWorld()->GetTimeSeconds() - GM->GetStageClearedTime();
		const float Alpha = FMath::Clamp(Age / 0.5f, 0.0f, 1.0f);
		const float CenterX = Canvas->ClipX * 0.5f, CenterY = Canvas->ClipY * 0.4f;

		DrawRect(FLinearColor(Panel.R, Panel.G, Panel.B, Panel.A * Alpha), 0.0f, CenterY - 90.0f * S, Canvas->ClipX, 180.0f * S);

		const bool bLast = GM->IsLastStage();
		DrawShadowedText(bLast ? TEXT("ALL STAGES CLEAR!") : TEXT("STAGE CLEAR!"), FLinearColor(Gold.R, Gold.G, Gold.B, Alpha), CenterX, CenterY - 20.0f * S, 3.0f * S, FVector2D(0.5f, 0.5f));
		const FString Time = FString::Printf(TEXT("TIME %s"), *FormatTime(GM->GetElapsedTime()));
		const FString Line = GM->IsNewRecord() && GM->GetPreviousBestTime() >= 0.0f
			? FString::Printf(TEXT("%s   NEW RECORD!"), *Time)
			: FString::Printf(TEXT("%s   %s"), *Time, bLast ? TEXT("Thanks for playing") : TEXT("Next stage..."));
		DrawShadowedText(Line, GM->IsNewRecord() && GM->GetPreviousBestTime() >= 0.0f ? FLinearColor(Record.R, Record.G, Record.B, Alpha) : FLinearColor(1.0f, 1.0f, 1.0f, 0.8f * Alpha), CenterX, CenterY + 45.0f * S, 1.1f * S, FVector2D(0.5f, 0.5f));

		// after the last stage, the whole run
		const UCoinDemoGameInstance* Instance = GetGameInstance<UCoinDemoGameInstance>();
		if (bLast && Instance && Instance->GetResults().Num() > 0)
		{
			const TArray<FStageResult>& Results = Instance->GetResults();
			const float RowH = 34.0f * S, BoxW = 520.0f * S;
			const float BoxH = (Results.Num() + 2) * RowH + 30.0f * S;
			const float BoxX = CenterX - BoxW * 0.5f, BoxY = CenterY + 110.0f * S;
			DrawRect(FLinearColor(Panel.R, Panel.G, Panel.B, Panel.A * Alpha), BoxX, BoxY, BoxW, BoxH);

			float Y = BoxY + 15.0f * S;
			for (const FStageResult& Result : Results)
			{
				DrawShadowedText(Result.Name.ToString(), FLinearColor(1.0f, 1.0f, 1.0f, 0.85f * Alpha), BoxX + 30.0f * S, Y, 0.95f * S);
				DrawShadowedText(FormatTime(Result.Time), FLinearColor(1.0f, 1.0f, 1.0f, 0.85f * Alpha), BoxX + BoxW - 30.0f * S, Y, 0.95f * S, FVector2D(1.0f, 0.0f));
				Y += RowH;
			}
			Y += 10.0f * S;
			DrawRect(FLinearColor(Gold.R, Gold.G, Gold.B, 0.6f * Alpha), BoxX + 30.0f * S, Y - 6.0f * S, BoxW - 60.0f * S, 2.0f * S);
			DrawShadowedText(TEXT("TOTAL"), FLinearColor(Gold.R, Gold.G, Gold.B, Alpha), BoxX + 30.0f * S, Y, 1.1f * S);
			DrawShadowedText(FormatTime(Instance->GetTotalTime()), FLinearColor(Gold.R, Gold.G, Gold.B, Alpha), BoxX + BoxW - 30.0f * S, Y, 1.1f * S, FVector2D(1.0f, 0.0f));
		}
	}
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
	};

	const float RowH = 34.0f * S;
	const float PanelW = 400.0f * S, PanelH = 70.0f * S + RowH * UE_ARRAY_COUNT(Controls);
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
	UFont* Font = GEngine->GetLargeFont();

	float Width = 0.0f, Height = 0.0f;
	GetTextSize(Text, Width, Height, Font, Scale);
	X -= Width * Align.X;
	Y -= Height * Align.Y;

	const float Offset = FMath::Max(1.0f, 2.0f * Scale);
	DrawText(Text, FLinearColor(0.0f, 0.0f, 0.0f, 0.6f * Color.A), X + Offset, Y + Offset, Font, Scale);
	DrawText(Text, Color, X, Y, Font, Scale);
}
