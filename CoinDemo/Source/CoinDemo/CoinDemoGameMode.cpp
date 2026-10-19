// Copyright Epic Games, Inc. All Rights Reserved.

#include "CoinDemoGameMode.h"
#include "CoinDemoHUD.h"
#include "CoinPickup.h"
#include "DevCapture.h"
#include "CoinDemoSaveGame.h"
#include "CoinDemoGameInstance.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialParameterCollection.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/Pawn.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

#define LOCTEXT_NAMESPACE "CoinDemo"

ACoinDemoGameMode::ACoinDemoGameMode()
{
	HUDClass = ACoinDemoHUD::StaticClass();
	DevCapture = CreateDefaultSubobject<UDevCapture>(TEXT("DevCapture"));

	static ConstructorHelpers::FObjectFinder<USoundBase> Clear(TEXT("/Game/Audio/SFX_Clear.SFX_Clear"));
	static ConstructorHelpers::FObjectFinder<USoundBase> Record(TEXT("/Game/Audio/SFX_Record.SFX_Record"));
	ClearSound = Clear.Object;
	RecordSound = Record.Object;

	static ConstructorHelpers::FObjectFinder<UMaterialParameterCollection> Barrier(TEXT("/Game/Stages/Common/MPC_Barrier.MPC_Barrier"));
	BarrierParameters = Barrier.Object;
	PrimaryActorTick.bCanEverTick = true;

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

	StageStartTime = GetWorld()->GetTimeSeconds();
	if (const float* Best = UCoinDemoSaveGame::LoadOrCreate()->BestTimes.Find(UGameplayStatics::GetCurrentLevelName(this, true)))
	{
		PreviousBestTime = *Best;
	}

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
	LastCoinTime = GetWorld()->GetTimeSeconds();

	BP_OnCoinCollected(CollectedCoins, TotalCoins);

	// was this the last coin?
	if (CollectedCoins >= TotalCoins && !IsStageCleared())
	{
		StageClearedTime = GetWorld()->GetTimeSeconds();

		// remember the best time per stage
		const float Time = GetElapsedTime();
		bNewRecord = PreviousBestTime < 0.0f || Time < PreviousBestTime;
		if (bNewRecord)
		{
			UCoinDemoSaveGame* SaveGame = UCoinDemoSaveGame::LoadOrCreate();
			SaveGame->BestTimes.Add(UGameplayStatics::GetCurrentLevelName(this, true), Time);
			SaveGame->Save();
		}

		if (UCoinDemoGameInstance* Instance = GetGameInstance<UCoinDemoGameInstance>())
		{
			// a run starts at the first stage
			if (GetStageNumber() == 1)
			{
				Instance->ResetRun();
			}
			Instance->AddResult(GetStageName(), Time);
		}

		if (USoundBase* Sound = (bNewRecord && PreviousBestTime >= 0.0f) ? RecordSound : ClearSound)
		{
			UGameplayStatics::PlaySound2D(this, Sound);
		}

		BP_OnStageCleared(IsLastStage());

		if (!IsLastStage())
		{
			GetWorldTimerManager().SetTimer(NextStageTimer, this, &ACoinDemoGameMode::OpenNextStage, FMath::Max(NextStageDelay, 0.01f), false);
		}
		else
		{
			GetWorldTimerManager().SetTimer(NextStageTimer, this, &ACoinDemoGameMode::OpenFirstStage, FMath::Max(RestartDelay, 0.01f), false);
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

void ACoinDemoGameMode::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Player)
	{
		return;
	}

	const FVector Location = Player->GetActorLocation();
	if (BarrierParameters)
	{
		UKismetMaterialLibrary::SetVectorParameterValue(this, BarrierParameters, TEXT("PlayerPosition"), FLinearColor(Location.X, Location.Y, Location.Z, 1.0f));
	}

	// fell through a gap in the scan: the character puts itself back at the start
	if (const AActor* Start = Player->GetController() ? FindPlayerStart(Player->GetController()) : nullptr;
		Start && Location.Z < Start->GetActorLocation().Z - FallLimit)
	{
		Player->FellOutOfWorld(*GetDefault<UDamageType>());
	}
}

float ACoinDemoGameMode::GetElapsedTime() const
{
	const float End = IsStageCleared() ? StageClearedTime : GetWorld()->GetTimeSeconds();
	return End - StageStartTime;
}

FText ACoinDemoGameMode::GetStageName() const
{
	const int32 Index = GetStageNumber() - 1;
	return StageNames.IsValidIndex(Index) ? StageNames[Index] : FText::FromString(UGameplayStatics::GetCurrentLevelName(this, true));
}

void ACoinDemoGameMode::RestartStage()
{
	UGameplayStatics::OpenLevel(this, FName(*UGameplayStatics::GetCurrentLevelName(this, true)));
}

void ACoinDemoGameMode::OpenFirstStage()
{
	if (Stages.Num() > 0)
	{
		UGameplayStatics::OpenLevelBySoftObjectPtr(this, Stages[0]);
	}
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
