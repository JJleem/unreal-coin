// Copyright Epic Games, Inc. All Rights Reserved.


#include "CoinDemoSaveGame.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/StrongObjectPtr.h"

const FString UCoinDemoSaveGame::SlotName(TEXT("CoinDemo"));

namespace CoinDemoSave
{
	/** One save object shared by the menus, the HUD and the game mode, so settings changes are seen everywhere */
	TStrongObjectPtr<UCoinDemoSaveGame> Cached;
}

UCoinDemoSaveGame* UCoinDemoSaveGame::LoadOrCreate()
{
	if (CoinDemoSave::Cached.IsValid())
	{
		return CoinDemoSave::Cached.Get();
	}

	UCoinDemoSaveGame* Save = Cast<UCoinDemoSaveGame>(UGameplayStatics::LoadGameFromSlot(SlotName, 0));
	if (!Save)
	{
		Save = Cast<UCoinDemoSaveGame>(UGameplayStatics::CreateSaveGameObject(StaticClass()));
	}
	CoinDemoSave::Cached.Reset(Save);
	return Save;
}

void UCoinDemoSaveGame::Save()
{
	UGameplayStatics::SaveGameToSlot(this, SlotName, 0);
}

EStageMedal UCoinDemoSaveGame::GetMedal(const FString& Stage) const
{
	const EStageMedal* Medal = BestMedals.Find(Stage);
	return Medal ? *Medal : EStageMedal::None;
}
