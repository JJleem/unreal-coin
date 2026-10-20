// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "CoinDemoSaveGame.generated.h"

/** Medals for a stage clear time, better is higher */
UENUM(BlueprintType)
enum class EStageMedal : uint8
{
	None,
	Bronze,
	Silver,
	Gold
};

/** The player's path through a stage, sampled at a fixed interval, replayed by the ghost */
USTRUCT()
struct FGhostTrack
{
	GENERATED_BODY()

	UPROPERTY()
	float Interval = 0.1f;

	UPROPERTY()
	TArray<FVector> Positions;

	UPROPERTY()
	TArray<float> Yaws;

	/** 1 while in the air, so the ghost plays the jump animation */
	UPROPERTY()
	TArray<uint8> Falling;

	void Reset() { Positions.Reset(); Yaws.Reset(); Falling.Reset(); }
	void Add(const FVector& Position, float Yaw, bool bFalling) { Positions.Add(Position); Yaws.Add(Yaw); Falling.Add(bFalling ? 1 : 0); }
	float GetDuration() const { return Positions.Num() * Interval; }
};

/**
 *  Persistent player progress and settings
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

	/** Best medal earned, by stage map name */
	UPROPERTY()
	TMap<FString, EStageMedal> BestMedals;

	/** Stages whose hidden gem was found */
	UPROPERTY()
	TSet<FString> Gems;

	/** The run behind each best time, by stage map name */
	UPROPERTY()
	TMap<FString, FGhostTrack> Ghosts;

	/** Settings */
	UPROPERTY()
	float MouseSensitivity = 1.0f;

	UPROPERTY()
	bool bInvertY = false;

	UPROPERTY()
	float MasterVolume = 1.0f;

	UPROPERTY()
	bool bShowGhost = true;

	/** Loads the save, or creates an empty one. The loaded object is cached for the session */
	static UCoinDemoSaveGame* LoadOrCreate();

	/** Writes the save to disk */
	void Save();

	/** Medal earned on a stage so far */
	EStageMedal GetMedal(const FString& Stage) const;

	/** True once the stage has been cleared at least once */
	bool IsCleared(const FString& Stage) const { return BestTimes.Contains(Stage); }
};
