// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "CoinDemoSaveGame.generated.h"

/**
 *  Persistent player progress: the best clear time of every stage
 */
UCLASS()
class UCoinDemoSaveGame : public USaveGame
{
	GENERATED_BODY()

public:

	/** Save slot used by the game */
	static const FString SlotName;

	/** Best clear time in seconds, by stage map name */
	UPROPERTY()
	TMap<FString, float> BestTimes;

	/** Loads the save, or creates an empty one */
	static UCoinDemoSaveGame* LoadOrCreate();

	/** Writes the save to disk */
	void Save();
};
