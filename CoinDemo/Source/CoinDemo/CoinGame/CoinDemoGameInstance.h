// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "CoinDemoGameInstance.generated.h"

/** One cleared stage of the current run */
USTRUCT()
struct FStageResult
{
	GENERATED_BODY()

	UPROPERTY()
	FText Name;

	UPROPERTY()
	float Time = 0.0f;
};

/**
 *  Lives across level loads and keeps the results of the current run, for the summary after the last stage
 */
UCLASS()
class UCoinDemoGameInstance : public UGameInstance
{
	GENERATED_BODY()

	/** Stages cleared in this run, in order */
	UPROPERTY()
	TArray<FStageResult> Results;

public:

	/** Records a cleared stage */
	void AddResult(const FText& Name, float Time) { Results.Add({ Name, Time }); }

	/** Clears the run, e.g. when starting over from the first stage */
	void ResetRun() { Results.Reset(); }

	const TArray<FStageResult>& GetResults() const { return Results; }

	/** Sum of all cleared stage times */
	float GetTotalTime() const;
};
