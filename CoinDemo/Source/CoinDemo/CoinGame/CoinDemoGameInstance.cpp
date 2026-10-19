// Copyright Epic Games, Inc. All Rights Reserved.


#include "CoinDemoGameInstance.h"

float UCoinDemoGameInstance::GetTotalTime() const
{
	float Total = 0.0f;
	for (const FStageResult& Result : Results)
	{
		Total += Result.Time;
	}
	return Total;
}
