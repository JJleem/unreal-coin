// Copyright Epic Games, Inc. All Rights Reserved.

#include "CoinDemoGameMode.h"
#include "CoinDemoHUD.h"
#include "CoinPickup.h"
#include "DevCapture.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

#define LOCTEXT_NAMESPACE "CoinDemo"

ACoinDemoGameMode::ACoinDemoGameMode()
{
	HUDClass = ACoinDemoHUD::StaticClass();
	DevCapture = CreateDefaultSubobject<UDevCapture>(TEXT("DevCapture"));

	// stage 1 is the template map, followed by the ANNX scan stages built by Scripts/build_scan_stages.py
	struct FStageInfo { const TCHAR* Level; FText Name; };
	const FStageInfo StageList[] = {
		{ TEXT("/Game/ThirdPerson/Lvl_ThirdPerson.Lvl_ThirdPerson"), LOCTEXT("Stage_Training", "연습장") },
		{ TEXT("/Game/Stages/Lvl_Hongdae.Lvl_Hongdae"), LOCTEXT("Stage_Hongdae", "홍대 거리") },
		{ TEXT("/Game/Stages/Lvl_Gyeonggijeon.Lvl_Gyeonggijeon"), LOCTEXT("Stage_Gyeonggijeon", "전주 경기전") },
		{ TEXT("/Game/Stages/Lvl_Gwanghwamun.Lvl_Gwanghwamun"), LOCTEXT("Stage_Gwanghwamun", "광화문 월대") },
		{ TEXT("/Game/Stages/Lvl_JejuPier.Lvl_JejuPier"), LOCTEXT("Stage_JejuPier", "제주 바닷가 포구") },
	};

	for (const FStageInfo& Stage : StageList)
	{
		Stages.Add(TSoftObjectPtr<UWorld>(FSoftObjectPath(Stage.Level)));
		StageNames.Add(Stage.Name);
	}
}

void ACoinDemoGameMode::BeginPlay()
{
	Super::BeginPlay();

	// count every coin placed in this stage
	TotalCoins = 0;
	for (TActorIterator<ACoinPickup> It(GetWorld()); It; ++It)
	{
		++TotalCoins;
	}
}

void ACoinDemoGameMode::CoinCollected()
{
	++CollectedCoins;

	BP_OnCoinCollected(CollectedCoins, TotalCoins);

	// was this the last coin?
	if (CollectedCoins >= TotalCoins && !IsStageCleared())
	{
		StageClearedTime = GetWorld()->GetTimeSeconds();

		BP_OnStageCleared(IsLastStage());

		if (!IsLastStage())
		{
			GetWorldTimerManager().SetTimer(NextStageTimer, this, &ACoinDemoGameMode::OpenNextStage, FMath::Max(NextStageDelay, 0.01f), false);
		}
	}
}

int32 ACoinDemoGameMode::GetStageNumber() const
{
	// match the current map name against the stage list, ignoring the PIE prefix
	const FString CurrentMap = UGameplayStatics::GetCurrentLevelName(this, true);

	for (int32 i = 0; i < Stages.Num(); ++i)
	{
		if (Stages[i].GetAssetName() == CurrentMap)
		{
			return i + 1;
		}
	}

	return 0;
}

FText ACoinDemoGameMode::GetStageName() const
{
	const int32 Index = GetStageNumber() - 1;
	return StageNames.IsValidIndex(Index) ? StageNames[Index] : FText::FromString(UGameplayStatics::GetCurrentLevelName(this, true));
}

void ACoinDemoGameMode::OpenNextStage()
{
	const int32 NextIndex = GetStageNumber();

	if (Stages.IsValidIndex(NextIndex))
	{
		UGameplayStatics::OpenLevelBySoftObjectPtr(this, Stages[NextIndex]);
	}
}

#undef LOCTEXT_NAMESPACE
