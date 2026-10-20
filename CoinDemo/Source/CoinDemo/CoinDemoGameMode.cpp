// Copyright Epic Games, Inc. All Rights Reserved.

#include "CoinDemoGameMode.h"
#include "CoinDemoHUD.h"
#include "CoinPickup.h"
#include "DevCapture.h"
#include "CoinDemoSaveGame.h"
#include "CoinDemoGameInstance.h"
#include "GemPickup.h"
#include "GhostRunner.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerStart.h"
#include "Camera/CameraActor.h"
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
	static ConstructorHelpers::FObjectFinder<USoundBase> Medal(TEXT("/Game/Audio/SFX_Medal.SFX_Medal"));
	ClearSound = Clear.Object;
	RecordSound = Record.Object;
	MedalSound = Medal.Object;

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

	TitleLevel = TSoftObjectPtr<UWorld>(FSoftObjectPath(TEXT("/Game/Stages/Lvl_Title.Lvl_Title")));
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

	const FString Stage = UGameplayStatics::GetCurrentLevelName(this, true);
	bHasGem = TActorIterator<AGemPickup>(GetWorld()) ? true : false;
	bGemFoundBefore = UCoinDemoSaveGame::LoadOrCreate()->Gems.Contains(Stage);

	ComputeMedalTimes();
	if (!IsTitleScreen())
	{
		StartGhost();
	}
	else if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		// circle the start of the stage
		for (TActorIterator<APlayerStart> It(GetWorld()); It; ++It)
		{
			TitleFocus = It->GetActorLocation();
			break;
		}
		TitleCamera = GetWorld()->SpawnActor<ACameraActor>(TitleFocus, FRotator::ZeroRotator);
		PC->SetViewTarget(TitleCamera);
	}

	// fade in from the previous stage
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0); PC && PC->PlayerCameraManager)
	{
		PC->PlayerCameraManager->StartCameraFade(1.0f, 0.0f, FadeTime, FLinearColor::Black);
	}
}

void ACoinDemoGameMode::HandleStartingNewPlayer_Implementation(APlayerController* NewPlayer)
{
	// the title screen has no player character, its camera is driven by the HUD's title view
	if (IsTitleScreen())
	{
		return;
	}
	Super::HandleStartingNewPlayer_Implementation(NewPlayer);
}

bool ACoinDemoGameMode::IsTitleScreen() const
{
	return UGameplayStatics::GetCurrentLevelName(this, true) == TitleLevel.GetAssetName();
}

void ACoinDemoGameMode::ComputeMedalTimes()
{
	// greedy tour from the start through every coin, a fair stand-in for a good route
	TArray<FVector> Coins;
	for (TActorIterator<ACoinPickup> It(GetWorld()); It; ++It)
	{
		Coins.Add(It->GetActorLocation());
	}
	FVector At = FVector::ZeroVector;
	for (TActorIterator<APlayerStart> It(GetWorld()); It; ++It)
	{
		At = It->GetActorLocation();
		break;
	}

	float Length = 0.0f, Climb = 0.0f;
	while (Coins.Num() > 0)
	{
		int32 Best = 0;
		for (int32 i = 1; i < Coins.Num(); ++i)
		{
			if (FVector::DistSquared(At, Coins[i]) < FVector::DistSquared(At, Coins[Best]))
			{
				Best = i;
			}
		}
		Length += FVector::Dist2D(At, Coins[Best]);
		Climb += FMath::Max(Coins[Best].Z - At.Z, 0.0f);
		At = Coins[Best];
		Coins.RemoveAtSwap(Best);
	}

	// gold: sprinting a slightly winding route, plus time for climbing; silver and bronze are more forgiving
	const float Gold = Length * 1.3f / 750.0f + Climb / 150.0f + 1.0f * TotalCoins + 2.0f;
	MedalTimes[0] = FMath::RoundToFloat(Gold);
	MedalTimes[1] = FMath::RoundToFloat(Gold * 1.5f);
	MedalTimes[2] = FMath::RoundToFloat(Gold * 2.3f);
}

float ACoinDemoGameMode::GetMedalTime(EStageMedal Medal) const
{
	switch (Medal)
	{
	case EStageMedal::Gold: return MedalTimes[0];
	case EStageMedal::Silver: return MedalTimes[1];
	case EStageMedal::Bronze: return MedalTimes[2];
	default: return 0.0f;
	}
}

EStageMedal ACoinDemoGameMode::GetMedalForTime(float Time) const
{
	return Time <= MedalTimes[0] ? EStageMedal::Gold
		: Time <= MedalTimes[1] ? EStageMedal::Silver
		: Time <= MedalTimes[2] ? EStageMedal::Bronze
		: EStageMedal::None;
}

void ACoinDemoGameMode::StartGhost()
{
	const UCoinDemoSaveGame* SaveGame = UCoinDemoSaveGame::LoadOrCreate();
	const FGhostTrack* Track = SaveGame->Ghosts.Find(UGameplayStatics::GetCurrentLevelName(this, true));
	if (!SaveGame->bShowGhost || !Track || Track->Positions.Num() < 2)
	{
		return;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Ghost = GetWorld()->SpawnActor<AGhostRunner>(Track->Positions[0], FRotator::ZeroRotator, Params);
	if (Ghost)
	{
		Ghost->Play(*Track, StageStartTime);
	}
}

void ACoinDemoGameMode::GemCollected()
{
	GemTime = GetWorld()->GetTimeSeconds();
	UCoinDemoSaveGame* SaveGame = UCoinDemoSaveGame::LoadOrCreate();
	SaveGame->Gems.Add(UGameplayStatics::GetCurrentLevelName(this, true));
	SaveGame->Save();
}

void ACoinDemoGameMode::CoinCollected()
{
	++CollectedCoins;

	// quick pickups chain into a combo that takes time off the clock
	const float Now = GetWorld()->GetTimeSeconds();
	Combo = Now - LastCoinTime < ComboWindow ? Combo + 1 : 1;
	LastBonus = Combo > 1 ? FMath::Min(ComboBonusStep * (Combo - 1), ComboBonusMax) : 0.0f;
	TimeBonus += LastBonus;
	LastCoinTime = Now;

	BP_OnCoinCollected(CollectedCoins, TotalCoins);

	// was this the last coin?
	if (CollectedCoins >= TotalCoins && !IsStageCleared())
	{
		StageClearedTime = GetWorld()->GetTimeSeconds();

		// remember the best time, its ghost and the best medal per stage
		const FString Stage = UGameplayStatics::GetCurrentLevelName(this, true);
		UCoinDemoSaveGame* SaveGame = UCoinDemoSaveGame::LoadOrCreate();
		const float Time = GetElapsedTime();
		bNewRecord = PreviousBestTime < 0.0f || Time < PreviousBestTime;
		if (bNewRecord)
		{
			SaveGame->BestTimes.Add(Stage, Time);
			SaveGame->Ghosts.Add(Stage, Recording);
		}
		ClearMedal = GetMedalForTime(Time);
		bNewMedal = ClearMedal > SaveGame->GetMedal(Stage);
		if (bNewMedal)
		{
			SaveGame->BestMedals.Add(Stage, ClearMedal);
		}
		SaveGame->Save();

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
		if (ClearMedal != EStageMedal::None && MedalSound)
		{
			// the medal lands just after the clear jingle
			FTimerHandle MedalTimer;
			GetWorldTimerManager().SetTimer(MedalTimer, FTimerDelegate::CreateWeakLambda(this, [this] { UGameplayStatics::PlaySound2D(this, MedalSound); }), 0.9f, false);
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

	if (TitleCamera)
	{
		// slow orbit, looking slightly down at the start
		const float Angle = GetWorld()->GetRealTimeSeconds() * 0.05f;
		const FVector Eye = TitleFocus + FVector(FMath::Cos(Angle) * 1300.0f, FMath::Sin(Angle) * 1300.0f, 450.0f);
		TitleCamera->SetActorLocationAndRotation(Eye, (TitleFocus + FVector(0.0f, 0.0f, 350.0f) - Eye).Rotation());
	}

	APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Player)
	{
		return;
	}

	const FVector Location = Player->GetActorLocation();

	// sample the run for the ghost
	const float Now = GetWorld()->GetTimeSeconds();
	if (!IsStageCleared() && Now >= NextRecordTime)
	{
		const ACharacter* Character = Cast<ACharacter>(Player);
		Recording.Add(Location, Player->GetActorRotation().Yaw, Character && Character->GetCharacterMovement()->IsFalling());
		NextRecordTime = StageStartTime + Recording.Positions.Num() * Recording.Interval;
	}

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
	return FMath::Max(End - StageStartTime - TimeBonus, 0.0f);
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

void ACoinDemoGameMode::FadeToLevel(const TSoftObjectPtr<UWorld>& Level)
{
	UGameplayStatics::SetGamePaused(this, false);
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC || !PC->PlayerCameraManager || FadeTime <= 0.0f)
	{
		UGameplayStatics::OpenLevelBySoftObjectPtr(this, Level);
		return;
	}

	PC->PlayerCameraManager->StartCameraFade(0.0f, 1.0f, FadeTime, FLinearColor::Black, false, true);
	FTimerHandle Timer;
	GetWorldTimerManager().SetTimer(Timer, FTimerDelegate::CreateWeakLambda(this, [this, Level]
	{
		UGameplayStatics::OpenLevelBySoftObjectPtr(this, Level);
	}), FadeTime, false);
}

void ACoinDemoGameMode::OpenStage(int32 StageNumber)
{
	if (Stages.IsValidIndex(StageNumber - 1))
	{
		FadeToLevel(Stages[StageNumber - 1]);
	}
}

void ACoinDemoGameMode::OpenTitle()
{
	FadeToLevel(TitleLevel);
}

void ACoinDemoGameMode::OpenFirstStage()
{
	OpenTitle();
}

void ACoinDemoGameMode::OpenNextStage()
{
	OpenStage(GetStageNumber() + 1);
}

FString ACoinDemoGameMode::GetStageMapName(int32 StageNumber) const
{
	return Stages.IsValidIndex(StageNumber - 1) ? Stages[StageNumber - 1].GetAssetName() : FString();
}

FText ACoinDemoGameMode::GetStageNameByNumber(int32 StageNumber) const
{
	return StageNames.IsValidIndex(StageNumber - 1) ? StageNames[StageNumber - 1] : FText::GetEmpty();
}

#undef LOCTEXT_NAMESPACE
