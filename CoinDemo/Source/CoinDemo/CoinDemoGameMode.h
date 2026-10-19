// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "CoinDemoGameMode.generated.h"

/**
 *  Simple GameMode for a third person game
 *  Counts the coins in the current stage and opens the next stage once all of them are collected
 */
UCLASS(abstract)
class ACoinDemoGameMode : public AGameModeBase
{
	GENERATED_BODY()

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

	/** Number of coins placed in the current stage */
	int32 TotalCoins = 0;

	/** Number of coins collected so far in the current stage */
	int32 CollectedCoins = 0;

	/** World time when the stage was cleared, or a negative value while it is in progress */
	float StageClearedTime = -1.0f;

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

protected:

	/** Counts the coins in the stage */
	virtual void BeginPlay() override;

	/** Opens the next stage */
	void OpenNextStage();

	/** Passes control to BP to update UI when a coin is collected */
	UFUNCTION(BlueprintImplementableEvent, Category="Stages", meta = (DisplayName = "On Coin Collected"))
	void BP_OnCoinCollected(int32 Collected, int32 Total);

	/** Passes control to BP to update UI when every coin in the stage is collected */
	UFUNCTION(BlueprintImplementableEvent, Category="Stages", meta = (DisplayName = "On Stage Cleared"))
	void BP_OnStageCleared(bool bWasLastStage);
};
