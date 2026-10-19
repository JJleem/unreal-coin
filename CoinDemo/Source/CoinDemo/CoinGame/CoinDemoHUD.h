// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "CoinDemoHUD.generated.h"

/**
 *  Draws the stage name, the coin counter and the stage clear banner
 *  Reads everything from ACoinDemoGameMode every frame, so it has no state of its own
 */
UCLASS()
class ACoinDemoHUD : public AHUD
{
	GENERATED_BODY()

public:

	/** Draws the HUD */
	virtual void DrawHUD() override;

protected:

	/** Draws the controls panel shown on the tutorial stage */
	void DrawTutorial(float S, int32 CoinCount);

	/** Draws text with a drop shadow, aligned by Align (0 = left/top, 0.5 = centre) */
	void DrawShadowedText(const FString& Text, const FLinearColor& Color, float X, float Y, float Scale, FVector2D Align = FVector2D::ZeroVector);
};
