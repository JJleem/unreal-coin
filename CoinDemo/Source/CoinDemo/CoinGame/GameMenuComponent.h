// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "GameMenuComponent.generated.h"

class UInputAction;
class UInputMappingContext;
class UEnhancedInputComponent;
class USoundBase;

/** Which menu is open */
UENUM()
enum class EGameMenu : uint8
{
	None,
	Title,
	StageSelect,
	Settings,
	Pause
};

/** One row of the open menu, as the HUD draws it */
struct FGameMenuItem
{
	/** Left column */
	FString Label;

	/** Right column: a setting's value, a stage's best time... */
	FString Value;

	/** Small second line */
	FString Detail;

	bool bEnabled = true;

	/** Settings rows change with left and right */
	bool bAdjustable = false;
};

/**
 *  Title, stage select, settings and pause menus for the player controller
 *  Keeps the menu state and reacts to the menu keys; ACoinDemoHUD draws it. The menu keys get their own input
 *  mapping context, added only while a menu is open so they never steal keys from the character.
 */
UCLASS(ClassGroup=(CoinDemo))
class UGameMenuComponent : public UActorComponent
{
	GENERATED_BODY()

	EGameMenu Menu = EGameMenu::None;

	/** Where Back goes from the settings */
	EGameMenu SettingsReturn = EGameMenu::None;

	int32 Selected = 0;

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> MenuContext;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> UpAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> DownAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LeftAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> RightAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> ConfirmAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> ClickAction;

	/** Escape: opens the pause menu in play, goes back in menus */
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> BackAction;

	UPROPERTY(Transient)
	TObjectPtr<USoundBase> MoveSound;

	UPROPERTY(Transient)
	TObjectPtr<USoundBase> SelectSound;

public:

	UGameMenuComponent();

	/** Creates the menu actions and binds them on the controller's input component */
	void BindInput(UEnhancedInputComponent* Input);

	/** Opens a menu, or closes the menus with None */
	void Open(EGameMenu NewMenu);

	EGameMenu GetMenu() const { return Menu; }
	int32 GetSelected() const { return Selected; }

	/** Selects a row, e.g. the one under the mouse */
	void Select(int32 Index);

	/** Rows of the open menu */
	TArray<FGameMenuItem> GetItems() const;

	/** Title of the open menu */
	FString GetTitle() const;

	/** Presses a menu key by name, for scripted checks: Up, Down, Left, Right, Confirm, Back */
	void RunCommand(const FString& Command);

	/** Applies the saved audio and look settings */
	static void ApplySettings(const UObject* WorldContext);

protected:

	virtual void BeginPlay() override;

	void OnUp();
	void OnDown();
	void OnLeft() { Adjust(-1); }
	void OnRight() { Adjust(1); }
	void OnConfirm();
	void OnClick();
	void OnBack();

	/** Changes the selected setting by Direction steps */
	void Adjust(int32 Direction);

	/** Runs the selected row */
	void Activate(int32 Index);

	class APlayerController* GetPlayerController() const;
	class ACoinDemoGameMode* GetGameMode() const;
	void PlayMenuSound(USoundBase* Sound) const;
};
