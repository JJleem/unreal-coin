// Copyright Epic Games, Inc. All Rights Reserved.


#include "CoinDemoSaveGame.h"
#include "Kismet/GameplayStatics.h"

const FString UCoinDemoSaveGame::SlotName(TEXT("CoinDemo"));

UCoinDemoSaveGame* UCoinDemoSaveGame::LoadOrCreate()
{
	if (UCoinDemoSaveGame* Loaded = Cast<UCoinDemoSaveGame>(UGameplayStatics::LoadGameFromSlot(SlotName, 0)))
	{
		return Loaded;
	}
	return Cast<UCoinDemoSaveGame>(UGameplayStatics::CreateSaveGameObject(StaticClass()));
}

void UCoinDemoSaveGame::Save()
{
	UGameplayStatics::SaveGameToSlot(this, SlotName, 0);
}
