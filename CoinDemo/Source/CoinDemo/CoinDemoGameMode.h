// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "CoinDemoSaveGame.h"
#include "CoinDemoGameMode.generated.h"

class USoundBase;

/**
 *  Simple GameMode for a third person game
 *  Counts the coins in the current stage and opens the next stage once all of them are collected
 */
UCLASS(abstract)
class ACoinDemoGameMode : public AGameModeBase
{
	GENERATED_BODY()

	/** Screenshots and scripted input for unattended checks, idle unless enabled on the command line */
	UPROPERTY(VisibleAnywhere, Category="Components")
	TObjectPtr<class UDevCapture> DevCapture;

protected:

	/** Stage maps in play order */
	UPROPERTY(EditDefaultsOnly, Category="Stages")
	TArray<TSoftObjectPtr<UWorld>> Stages;

	/** Title screen map: a scan stage without coins, seen from a slowly circling camera */
	UPROPERTY(EditDefaultsOnly, Category="Stages")
	TSoftObjectPtr<UWorld> TitleLevel;

	/** Circling camera of the title screen */
	UPROPERTY(Transient)
	TObjectPtr<class ACameraActor> TitleCamera;

	/** Point the title camera circles around */
	FVector TitleFocus = FVector::ZeroVector;

	/** Display names of the stages, in the same order as Stages */
	UPROPERTY(EditDefaultsOnly, Category="Stages")
	TArray<FText> StageNames;

	/** Seconds to wait after the last coin before opening the next stage */
	UPROPERTY(EditDefaultsOnly, Category="Stages", meta = (ClampMin = 0))
	float NextStageDelay = 3.0f;

	/** Seconds the run summary stays up after the last stage before starting over */
	UPROPERTY(EditDefaultsOnly, Category="Stages", meta = (ClampMin = 0))
	float RestartDelay = 12.0f;

	/** Number of coins placed in the current stage */
	int32 TotalCoins = 0;

	/** Number of coins collected so far in the current stage */
	int32 CollectedCoins = 0;

	/** World time when the stage was cleared, or a negative value while it is in progress */
	float StageClearedTime = -1.0f;

	/** World time when the stage started */
	float StageStartTime = 0.0f;

	/** World time of the last coin pickup, for UI feedback */
	float LastCoinTime = -100.0f;

	/** Coins picked up in quick succession; each one past the first takes time off the clock */
	int32 Combo = 0;

	/** Seconds taken off the clock by combos so far, and by the latest combo coin */
	float TimeBonus = 0.0f;
	float LastBonus = 0.0f;

	/** A coin within this many seconds of the previous one continues the combo */
	UPROPERTY(EditDefaultsOnly, Category="Stages|Combo", meta = (Units = "s"))
	float ComboWindow = 3.0f;

	/** Seconds off the clock per combo step, growing with the combo up to ComboBonusMax */
	UPROPERTY(EditDefaultsOnly, Category="Stages|Combo", meta = (Units = "s"))
	float ComboBonusStep = 0.5f;

	UPROPERTY(EditDefaultsOnly, Category="Stages|Combo", meta = (Units = "s"))
	float ComboBonusMax = 2.0f;

	/** Best clear time of this stage before this run, or a negative value if it was never cleared */
	float PreviousBestTime = -1.0f;

	/** True when this run set a new best time */
	bool bNewRecord = false;

	UPROPERTY(EditDefaultsOnly, Category="Stages|Audio")
	TObjectPtr<USoundBase> ClearSound;

	UPROPERTY(EditDefaultsOnly, Category="Stages|Audio")
	TObjectPtr<USoundBase> RecordSound;

	/** A player this far below their start has fallen out of the scan and is put back */
	UPROPERTY(EditDefaultsOnly, Category="Stages", meta = (Units = "cm"))
	float FallLimit = 2000.0f;

	/** Receives the player position every frame, so barriers can reveal themselves near the player */
	UPROPERTY(EditDefaultsOnly, Category="Stages")
	TObjectPtr<class UMaterialParameterCollection> BarrierParameters;

	/** Timer that opens the next stage */
	FTimerHandle NextStageTimer;

	/** Clear times for the medals, worked out from the coin layout when the stage starts */
	float MedalTimes[3] = { 0.0f, 0.0f, 0.0f };

	/** Medal earned by this clear, and whether it beats the stage's best medal */
	EStageMedal ClearMedal = EStageMedal::None;
	bool bNewMedal = false;

	/** Hidden gem state */
	bool bHasGem = false;
	bool bGemFoundBefore = false;
	float GemTime = -100.0f;

	/** The player's path through this run, saved as the ghost when it sets a best time */
	FGhostTrack Recording;
	float NextRecordTime = 0.0f;

	UPROPERTY(Transient)
	TObjectPtr<class AGhostRunner> Ghost;

	UPROPERTY(EditDefaultsOnly, Category="Stages|Audio")
	TObjectPtr<USoundBase> MedalSound;

	/** Seconds of the fade between stages */
	UPROPERTY(EditDefaultsOnly, Category="Stages", meta = (Units = "s"))
	float FadeTime = 0.6f;

public:

	/** Constructor */
	ACoinDemoGameMode();

	/** Called by a coin when the player collects it */
	void CoinCollected();

	/** Returns the number of coins placed in the current stage */
	UFUNCTION(BlueprintPure, Category="Stages")
	int32 GetTotalCoins() const { return TotalCoins; }

	/** Returns the number of coins collected in the current stage */
	UFUNCTION(BlueprintPure, Category="Stages")
	int32 GetCollectedCoins() const { return CollectedCoins; }

	/** Returns the 1-based number of the current stage, or 0 if the current map is not in the stage list */
	UFUNCTION(BlueprintPure, Category="Stages")
	int32 GetStageNumber() const;

	/** Returns the number of stages */
	UFUNCTION(BlueprintPure, Category="Stages")
	int32 GetStageCount() const { return Stages.Num(); }

	/** Returns the display name of the current stage */
	UFUNCTION(BlueprintPure, Category="Stages")
	FText GetStageName() const;

	/** Returns true once every coin in the stage is collected */
	UFUNCTION(BlueprintPure, Category="Stages")
	bool IsStageCleared() const { return StageClearedTime >= 0.0f; }

	/** Returns true when the cleared stage is the last one */
	UFUNCTION(BlueprintPure, Category="Stages")
	bool IsLastStage() const { return !Stages.IsValidIndex(GetStageNumber()); }

	/** Returns the world time when the stage was cleared, or a negative value while it is in progress */
	float GetStageClearedTime() const { return StageClearedTime; }

	/** Seconds spent in this stage, frozen once it is cleared */
	UFUNCTION(BlueprintPure, Category="Stages")
	float GetElapsedTime() const;

	/** Best clear time before this run, or a negative value if the stage was never cleared */
	float GetPreviousBestTime() const { return PreviousBestTime; }

	/** True when this run beat the previous best time */
	bool IsNewRecord() const { return bNewRecord; }

	/** World time of the last coin pickup */
	float GetLastCoinTime() const { return LastCoinTime; }

	/** Current combo, 1 for a single coin */
	int32 GetCombo() const { return Combo; }

	/** Seconds taken off by the latest combo coin, 0 if it didn't continue a combo */
	float GetLastBonus() const { return LastBonus; }

	/** True while another coin would still continue the combo */
	bool IsComboActive() const { return Combo > 1 && GetWorld()->GetTimeSeconds() - LastCoinTime < ComboWindow; }

	/** Fraction of the combo window left, 1 right after a coin */
	float GetComboTimeLeft() const { return FMath::Clamp(1.0f - (GetWorld()->GetTimeSeconds() - LastCoinTime) / ComboWindow, 0.0f, 1.0f); }

	/** World time when the stage started */
	float GetStageStartTime() const { return StageStartTime; }

	/** Reloads the current stage */
	UFUNCTION(BlueprintCallable, Category="Stages")
	void RestartStage();

	/** Opens a stage by its 1-based number, fading out first */
	void OpenStage(int32 StageNumber);

	/** Opens the title screen */
	void OpenTitle();

	/** True on the title screen, which shows a stage as backdrop without a player */
	bool IsTitleScreen() const;

	/** Clear time in seconds needed for a medal: Gold, Silver or Bronze */
	float GetMedalTime(EStageMedal Medal) const;

	/** The medal a clear time earns on this stage */
	EStageMedal GetMedalForTime(float Time) const;

	/** The medal this clear earned, and whether it was better than before */
	EStageMedal GetClearMedal() const { return ClearMedal; }
	bool IsNewMedal() const { return bNewMedal; }

	/** Called by the gem when the player picks it up */
	void GemCollected();

	/** True when this stage hides a gem */
	bool HasGem() const { return bHasGem; }

	/** True when the gem of this stage was found in an earlier run */
	bool WasGemFoundBefore() const { return bGemFoundBefore; }

	/** World time the gem was picked up in this run */
	float GetGemTime() const { return GemTime; }

	/** Level name of a stage, by 1-based number */
	FString GetStageMapName(int32 StageNumber) const;

	/** Display name of a stage, by 1-based number */
	FText GetStageNameByNumber(int32 StageNumber) const;

protected:

	/** Counts the coins in the stage */
	virtual void BeginPlay() override;

	/** Feeds the player position to the barrier material */
	virtual void Tick(float DeltaSeconds) override;

	/** Spawns the ghost of the best run, if there is one */
	void StartGhost();

	/** Works out the medal times from the shortest tour through the coins */
	void ComputeMedalTimes();

	/** Opens the next stage */
	void OpenNextStage();

	/** Fades the screen out, then opens Level */
	void FadeToLevel(const TSoftObjectPtr<UWorld>& Level);

	/** No pawn on the title screen */
	virtual void HandleStartingNewPlayer_Implementation(APlayerController* NewPlayer) override;

	/** Starts a new run from the first stage */
	void OpenFirstStage();

	/** Passes control to BP to update UI when a coin is collected */
	UFUNCTION(BlueprintImplementableEvent, Category="Stages", meta = (DisplayName = "On Coin Collected"))
	void BP_OnCoinCollected(int32 Collected, int32 Total);

	/** Passes control to BP to update UI when every coin in the stage is collected */
	UFUNCTION(BlueprintImplementableEvent, Category="Stages", meta = (DisplayName = "On Stage Cleared"))
	void BP_OnStageCleared(bool bWasLastStage);
};
