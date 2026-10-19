// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
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

	/** World time when the stage started */
	float GetStageStartTime() const { return StageStartTime; }

	/** Reloads the current stage */
	UFUNCTION(BlueprintCallable, Category="Stages")
	void RestartStage();

protected:

	/** Counts the coins in the stage */
	virtual void BeginPlay() override;

	/** Feeds the player position to the barrier material */
	virtual void Tick(float DeltaSeconds) override;

	/** Opens the next stage */
	void OpenNextStage();

	/** Starts a new run from the first stage */
	void OpenFirstStage();

	/** Passes control to BP to update UI when a coin is collected */
	UFUNCTION(BlueprintImplementableEvent, Category="Stages", meta = (DisplayName = "On Coin Collected"))
	void BP_OnCoinCollected(int32 Collected, int32 Total);

	/** Passes control to BP to update UI when every coin in the stage is collected */
	UFUNCTION(BlueprintImplementableEvent, Category="Stages", meta = (DisplayName = "On Stage Cleared"))
	void BP_OnStageCleared(bool bWasLastStage);
};
