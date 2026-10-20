// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "CoinDemoSaveGame.h"
#include "GameMenuComponent.h"
#include "CoinDemoHUD.generated.h"

class ACoinDemoGameMode;
class UGameMenuComponent;

/**
 *  Draws the game's whole interface on the canvas: the stage panel, compass, combo, medals and gem, the stage
 *  clear banner and run summary, and the menus kept by UGameMenuComponent.
 *  Reads everything from the game mode and the menu every frame; the only state it keeps is where it drew the
 *  menu rows, for the mouse.
 */
UCLASS()
class ACoinDemoHUD : public AHUD
{
	GENERATED_BODY()

	/** Screen rectangles of the menu rows drawn this frame (x, y, width, height) */
	TArray<FVector4f> MenuRects;

	/** Mouse position last frame, so hovering only changes the selection when the mouse actually moves */
	FVector2D LastMouse = FVector2D(-1.0f, -1.0f);

	/** The menu drawn last frame and the real time it appeared */
	EGameMenu ShownMenu = EGameMenu::None;
	float MenuShownTime = 0.0f;

public:

	/** Draws the HUD */
	virtual void DrawHUD() override;

	/** Index of the menu row under the mouse, or INDEX_NONE */
	int32 GetMenuItemAtMouse() const;

protected:

	/** Stage name, coins, timer, medal target and gem, top left */
	void DrawStagePanel(const ACoinDemoGameMode* GM, float S);

	/** Draws a bar along the top with markers for the remaining coins, by direction from the camera */
	void DrawCompass(float S);

	/** Draws the combo counter and the time it took off the clock */
	void DrawCombo(float S, float X, float Y);

	/** Big stage name for the first seconds of a stage */
	void DrawTitleCard(const ACoinDemoGameMode* GM, float S);

	/** Short messages in the middle of the screen: gem found, smash hints */
	void DrawPrompts(const ACoinDemoGameMode* GM, float S);

	/** Stage clear banner, medal and, after the last stage, the run summary */
	void DrawClear(const ACoinDemoGameMode* GM, float S);

	/** Game logo on the title screen */
	void DrawLogo(float S);

	/** The open menu */
	void DrawMenu(UGameMenuComponent* Menu, float S);

	/** Draws a square turned 45 degrees, centred on X, Y */
	void DrawDiamond(float X, float Y, float Size, const FLinearColor& Color);

	/** Draws the controls panel shown on the tutorial stage */
	void DrawTutorial(float S, int32 CoinCount);

	/** Draws text with a drop shadow, aligned by Align (0 = left/top, 0.5 = centre) */
	void DrawShadowedText(const FString& Text, const FLinearColor& Color, float X, float Y, float Scale, FVector2D Align = FVector2D::ZeroVector);

	/** Medal name and color */
	static FString MedalName(EStageMedal Medal);
	static FLinearColor MedalColor(EStageMedal Medal);
};
