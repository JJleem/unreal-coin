// Copyright Epic Games, Inc. All Rights Reserved.


#include "GameMenuComponent.h"
#include "CoinDemoGameMode.h"
#include "CoinDemoHUD.h"
#include "CoinDemoSaveGame.h"
#include "AudioDevice.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/GameUserSettings.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

namespace GameMenu
{
	const TCHAR* Medals[] = { TEXT("-"), TEXT("동메달"), TEXT("은메달"), TEXT("금메달") };
	const TCHAR* Quality[] = { TEXT("낮음"), TEXT("중간"), TEXT("높음"), TEXT("최고") };

	FString OnOff(bool bOn) { return bOn ? TEXT("켜기") : TEXT("끄기"); }

	FString FormatTime(float Seconds)
	{
		const int32 Minutes = FMath::FloorToInt(Seconds / 60.0f);
		return FString::Printf(TEXT("%d:%05.2f"), Minutes, Seconds - Minutes * 60.0f);
	}

	/** Settings rows, in order */
	enum ESetting { Sensitivity, InvertY, Volume, Graphics, Fullscreen, Ghost, SettingsBack, SettingCount };
}

UGameMenuComponent::UGameMenuComponent()
{
	static ConstructorHelpers::FObjectFinder<USoundBase> Tick(TEXT("/Game/Audio/SFX_Tick.SFX_Tick"));
	static ConstructorHelpers::FObjectFinder<USoundBase> Select(TEXT("/Game/Audio/SFX_Select.SFX_Select"));
	MoveSound = Tick.Object;
	SelectSound = Select.Object;
}

APlayerController* UGameMenuComponent::GetPlayerController() const
{
	return Cast<APlayerController>(GetOwner());
}

ACoinDemoGameMode* UGameMenuComponent::GetGameMode() const
{
	return GetWorld() ? GetWorld()->GetAuthGameMode<ACoinDemoGameMode>() : nullptr;
}

void UGameMenuComponent::PlayMenuSound(USoundBase* Sound) const
{
	if (Sound)
	{
		UGameplayStatics::PlaySound2D(this, Sound, 0.6f);
	}
}

void UGameMenuComponent::BindInput(UEnhancedInputComponent* Input)
{
	if (!Input || MenuContext)
	{
		return;
	}

	// menu keys work while the game is paused
	auto MakeAction = [this](const TCHAR* Name)
	{
		UInputAction* Action = NewObject<UInputAction>(this, Name);
		Action->ValueType = EInputActionValueType::Boolean;
		Action->bTriggerWhenPaused = true;
		return Action;
	};
	UpAction = MakeAction(TEXT("IA_MenuUp"));
	DownAction = MakeAction(TEXT("IA_MenuDown"));
	LeftAction = MakeAction(TEXT("IA_MenuLeft"));
	RightAction = MakeAction(TEXT("IA_MenuRight"));
	ConfirmAction = MakeAction(TEXT("IA_MenuConfirm"));
	ClickAction = MakeAction(TEXT("IA_MenuClick"));
	BackAction = MakeAction(TEXT("IA_MenuBack"));

	MenuContext = NewObject<UInputMappingContext>(this, TEXT("IMC_Menu"));
	for (const FKey& Key : { EKeys::Up, EKeys::W, EKeys::Gamepad_DPad_Up, EKeys::Gamepad_LeftStick_Up })
	{
		MenuContext->MapKey(UpAction, Key);
	}
	for (const FKey& Key : { EKeys::Down, EKeys::S, EKeys::Gamepad_DPad_Down, EKeys::Gamepad_LeftStick_Down })
	{
		MenuContext->MapKey(DownAction, Key);
	}
	for (const FKey& Key : { EKeys::Left, EKeys::A, EKeys::Gamepad_DPad_Left, EKeys::Gamepad_LeftStick_Left })
	{
		MenuContext->MapKey(LeftAction, Key);
	}
	for (const FKey& Key : { EKeys::Right, EKeys::D, EKeys::Gamepad_DPad_Right, EKeys::Gamepad_LeftStick_Right })
	{
		MenuContext->MapKey(RightAction, Key);
	}
	for (const FKey& Key : { EKeys::Enter, EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom })
	{
		MenuContext->MapKey(ConfirmAction, Key);
	}
	MenuContext->MapKey(ClickAction, EKeys::LeftMouseButton);
	MenuContext->MapKey(BackAction, EKeys::Gamepad_FaceButton_Right);

	Input->BindAction(UpAction, ETriggerEvent::Started, this, &UGameMenuComponent::OnUp);
	Input->BindAction(DownAction, ETriggerEvent::Started, this, &UGameMenuComponent::OnDown);
	Input->BindAction(LeftAction, ETriggerEvent::Started, this, &UGameMenuComponent::OnLeft);
	Input->BindAction(RightAction, ETriggerEvent::Started, this, &UGameMenuComponent::OnRight);
	Input->BindAction(ConfirmAction, ETriggerEvent::Started, this, &UGameMenuComponent::OnConfirm);
	Input->BindAction(ClickAction, ETriggerEvent::Started, this, &UGameMenuComponent::OnClick);
	Input->BindAction(BackAction, ETriggerEvent::Started, this, &UGameMenuComponent::OnBack);

	// Escape (and Start) always works: pause in play, back in menus. It lives in its own always-on context
	UInputAction* PauseAction = MakeAction(TEXT("IA_Pause"));
	UInputMappingContext* PauseContext = NewObject<UInputMappingContext>(this, TEXT("IMC_Pause"));
	PauseContext->MapKey(PauseAction, EKeys::Escape);
	PauseContext->MapKey(PauseAction, EKeys::P);
	PauseContext->MapKey(PauseAction, EKeys::Gamepad_Special_Right);
	Input->BindAction(PauseAction, ETriggerEvent::Started, this, &UGameMenuComponent::OnBack);
	if (const APlayerController* PC = GetPlayerController())
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			Subsystem->AddMappingContext(PauseContext, 5);

			// a menu opened before input was ready, e.g. the title menu from BeginPlay
			if (Menu != EGameMenu::None)
			{
				Subsystem->AddMappingContext(MenuContext, 10);
			}
		}
	}
}

void UGameMenuComponent::BeginPlay()
{
	Super::BeginPlay();

	ApplySettings(this);

	// the title screen opens straight into its menu
	if (const ACoinDemoGameMode* GM = GetGameMode(); GM && GM->IsTitleScreen())
	{
		Open(EGameMenu::Title);
	}
}

void UGameMenuComponent::ApplySettings(const UObject* WorldContext)
{
	const UCoinDemoSaveGame* SaveGame = UCoinDemoSaveGame::LoadOrCreate();
	if (const UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr)
	{
		if (FAudioDeviceHandle Audio = World->GetAudioDevice())
		{
			Audio->SetTransientPrimaryVolume(SaveGame->MasterVolume);
		}
	}
}

void UGameMenuComponent::Open(EGameMenu NewMenu)
{
	APlayerController* PC = GetPlayerController();
	if (!PC)
	{
		return;
	}

	const EGameMenu Previous = Menu;
	Menu = NewMenu;
	Selected = 0;

	// the stage select starts on the furthest unlocked stage
	if (Menu == EGameMenu::StageSelect)
	{
		for (int32 i = GetItems().Num() - 2; i >= 0; --i)
		{
			if (GetItems()[i].bEnabled)
			{
				Selected = i;
				break;
			}
		}
	}

	// menu keys only while a menu is open, so they never take W, S or Space from the character
	UEnhancedInputLocalPlayerSubsystem* Subsystem = PC->GetLocalPlayer() ? ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()) : nullptr;
	if (Subsystem && MenuContext)
	{
		if (Menu != EGameMenu::None && Previous == EGameMenu::None)
		{
			Subsystem->AddMappingContext(MenuContext, 10);
		}
		else if (Menu == EGameMenu::None && Previous != EGameMenu::None)
		{
			Subsystem->RemoveMappingContext(MenuContext);
		}
	}

	const bool bTitle = GetGameMode() && GetGameMode()->IsTitleScreen();
	UGameplayStatics::SetGamePaused(this, Menu != EGameMenu::None && !bTitle);
	PC->SetShowMouseCursor(Menu != EGameMenu::None);
	if (Menu != EGameMenu::None)
	{
		FInputModeGameAndUI Mode;
		Mode.SetHideCursorDuringCapture(false);
		PC->SetInputMode(Mode);
	}
	else
	{
		PC->SetInputMode(FInputModeGameOnly());
	}
}

void UGameMenuComponent::RunCommand(const FString& Command)
{
	if (Command == TEXT("Up")) { OnUp(); }
	else if (Command == TEXT("Down")) { OnDown(); }
	else if (Command == TEXT("Left")) { OnLeft(); }
	else if (Command == TEXT("Right")) { OnRight(); }
	else if (Command == TEXT("Confirm")) { OnConfirm(); }
	else if (Command == TEXT("Back")) { OnBack(); }
}

void UGameMenuComponent::Select(int32 Index)
{
	const TArray<FGameMenuItem> Items = GetItems();
	if (Items.IsValidIndex(Index) && Index != Selected)
	{
		Selected = Index;
		PlayMenuSound(MoveSound);
	}
}

void UGameMenuComponent::OnUp()
{
	const int32 Count = GetItems().Num();
	if (Menu != EGameMenu::None && Count > 0)
	{
		Selected = (Selected + Count - 1) % Count;
		PlayMenuSound(MoveSound);
	}
}

void UGameMenuComponent::OnDown()
{
	const int32 Count = GetItems().Num();
	if (Menu != EGameMenu::None && Count > 0)
	{
		Selected = (Selected + 1) % Count;
		PlayMenuSound(MoveSound);
	}
}

void UGameMenuComponent::OnConfirm()
{
	Activate(Selected);
}

void UGameMenuComponent::OnClick()
{
	const APlayerController* PC = GetPlayerController();
	const ACoinDemoHUD* HUD = PC ? Cast<ACoinDemoHUD>(PC->GetHUD()) : nullptr;
	const int32 Index = HUD ? HUD->GetMenuItemAtMouse() : INDEX_NONE;
	if (Index != INDEX_NONE)
	{
		Selected = Index;
		Activate(Index);
	}
}

void UGameMenuComponent::OnBack()
{
	switch (Menu)
	{
	case EGameMenu::None:
		// pausing is only for stages in progress
		if (const ACoinDemoGameMode* GM = GetGameMode(); GM && !GM->IsTitleScreen() && !GM->IsStageCleared())
		{
			PlayMenuSound(SelectSound);
			Open(EGameMenu::Pause);
		}
		break;
	case EGameMenu::Pause:
		Open(EGameMenu::None);
		break;
	case EGameMenu::StageSelect:
		Open(EGameMenu::Title);
		break;
	case EGameMenu::Settings:
		// back onto the Settings row of the menu we came from
		Open(SettingsReturn);
		Selected = 2;
		break;
	default:
		break;
	}
}

void UGameMenuComponent::Adjust(int32 Direction)
{
	if (Menu != EGameMenu::Settings)
	{
		return;
	}

	using namespace GameMenu;
	UCoinDemoSaveGame* SaveGame = UCoinDemoSaveGame::LoadOrCreate();
	UGameUserSettings* Settings = UGameUserSettings::GetGameUserSettings();
	switch (Selected)
	{
	case Sensitivity:
		SaveGame->MouseSensitivity = FMath::Clamp(FMath::RoundToFloat((SaveGame->MouseSensitivity + 0.1f * Direction) * 10.0f) / 10.0f, 0.2f, 3.0f);
		break;
	case InvertY:
		SaveGame->bInvertY = !SaveGame->bInvertY;
		break;
	case Volume:
		SaveGame->MasterVolume = FMath::Clamp(FMath::RoundToFloat((SaveGame->MasterVolume + 0.1f * Direction) * 10.0f) / 10.0f, 0.0f, 1.0f);
		break;
	case Graphics:
		if (Settings)
		{
			Settings->SetOverallScalabilityLevel(FMath::Clamp(Settings->GetOverallScalabilityLevel() + Direction, 0, 3));
			Settings->ApplySettings(false);
		}
		break;
	case Fullscreen:
		if (Settings)
		{
			Settings->SetFullscreenMode(Settings->GetFullscreenMode() == EWindowMode::Windowed ? EWindowMode::WindowedFullscreen : EWindowMode::Windowed);
			Settings->ApplySettings(false);
		}
		break;
	case Ghost:
		SaveGame->bShowGhost = !SaveGame->bShowGhost;
		break;
	default:
		return;
	}

	SaveGame->Save();
	ApplySettings(this);
	PlayMenuSound(MoveSound);
}

void UGameMenuComponent::Activate(int32 Index)
{
	ACoinDemoGameMode* GM = GetGameMode();
	const TArray<FGameMenuItem> Items = GetItems();
	if (!GM || !Items.IsValidIndex(Index) || !Items[Index].bEnabled)
	{
		return;
	}
	PlayMenuSound(SelectSound);

	switch (Menu)
	{
	case EGameMenu::Title:
		switch (Index)
		{
		case 0: Open(EGameMenu::None); GM->OpenStage(1); break;
		case 1: Open(EGameMenu::StageSelect); break;
		case 2: SettingsReturn = EGameMenu::Title; Open(EGameMenu::Settings); break;
		case 3: UKismetSystemLibrary::QuitGame(this, GetPlayerController(), EQuitPreference::Quit, false); break;
		}
		break;

	case EGameMenu::StageSelect:
		if (Index == Items.Num() - 1)
		{
			Open(EGameMenu::Title);
		}
		else
		{
			Open(EGameMenu::None);
			GM->OpenStage(Index + 1);
		}
		break;

	case EGameMenu::Settings:
		if (Index == GameMenu::SettingsBack)
		{
			OnBack();
		}
		else
		{
			Adjust(1);
		}
		break;

	case EGameMenu::Pause:
		switch (Index)
		{
		case 0: Open(EGameMenu::None); break;
		case 1: Open(EGameMenu::None); GM->RestartStage(); break;
		case 2: SettingsReturn = EGameMenu::Pause; Open(EGameMenu::Settings); break;
		case 3: Open(EGameMenu::None); GM->OpenTitle(); break;
		}
		break;

	default:
		break;
	}
}

FString UGameMenuComponent::GetTitle() const
{
	switch (Menu)
	{
	case EGameMenu::StageSelect: return TEXT("스테이지 선택");
	case EGameMenu::Settings: return TEXT("설정");
	case EGameMenu::Pause: return TEXT("일시정지");
	default: return FString();
	}
}

TArray<FGameMenuItem> UGameMenuComponent::GetItems() const
{
	using namespace GameMenu;
	TArray<FGameMenuItem> Items;
	const ACoinDemoGameMode* GM = GetGameMode();
	const UCoinDemoSaveGame* SaveGame = UCoinDemoSaveGame::LoadOrCreate();

	auto Add = [&Items](const FString& Label, const FString& Value = FString(), const FString& Detail = FString(), bool bEnabled = true, bool bAdjustable = false)
	{
		Items.Add({ Label, Value, Detail, bEnabled, bAdjustable });
	};

	switch (Menu)
	{
	case EGameMenu::Title:
		Add(TEXT("처음부터 시작"));
		Add(TEXT("스테이지 선택"));
		Add(TEXT("설정"));
		Add(TEXT("종료"));
		break;

	case EGameMenu::StageSelect:
		if (GM)
		{
			for (int32 Stage = 1; Stage <= GM->GetStageCount(); ++Stage)
			{
				const FString Map = GM->GetStageMapName(Stage);
				const bool bUnlocked = Stage == 1 || SaveGame->IsCleared(GM->GetStageMapName(Stage - 1));
				const float* Best = SaveGame->BestTimes.Find(Map);
				const FString Gem = SaveGame->Gems.Contains(Map) ? TEXT("  ·  보석 발견") : FString();
				Add(FString::Printf(TEXT("%d. %s"), Stage, *GM->GetStageNameByNumber(Stage).ToString()),
					bUnlocked ? (Best ? FormatTime(*Best) : TEXT("미완료")) : TEXT("잠김"),
					bUnlocked ? FString::Printf(TEXT("%s%s"), Medals[static_cast<int32>(SaveGame->GetMedal(Map))], *Gem) : TEXT("이전 스테이지를 클리어하세요"),
					bUnlocked);
			}
		}
		Add(TEXT("돌아가기"));
		break;

	case EGameMenu::Settings:
	{
		const UGameUserSettings* Settings = UGameUserSettings::GetGameUserSettings();
		const int32 Level = Settings ? FMath::Clamp(Settings->GetOverallScalabilityLevel(), 0, 3) : 3;
		Add(TEXT("마우스 감도"), FString::Printf(TEXT("◀  %.1f  ▶"), SaveGame->MouseSensitivity), FString(), true, true);
		Add(TEXT("상하 반전"), FString::Printf(TEXT("◀  %s  ▶"), *OnOff(SaveGame->bInvertY)), FString(), true, true);
		Add(TEXT("음량"), FString::Printf(TEXT("◀  %d%%  ▶"), FMath::RoundToInt(SaveGame->MasterVolume * 100.0f)), FString(), true, true);
		Add(TEXT("그래픽 품질"), FString::Printf(TEXT("◀  %s  ▶"), Quality[Level]), TEXT("스캔 화질에는 영향이 없습니다"), true, true);
		Add(TEXT("전체 화면"), FString::Printf(TEXT("◀  %s  ▶"), *OnOff(Settings && Settings->GetFullscreenMode() != EWindowMode::Windowed)), FString(), true, true);
		Add(TEXT("고스트 표시"), FString::Printf(TEXT("◀  %s  ▶"), *OnOff(SaveGame->bShowGhost)), TEXT("최고 기록의 움직임을 반투명하게 보여줍니다"), true, true);
		Add(TEXT("돌아가기"));
		break;
	}

	case EGameMenu::Pause:
		Add(TEXT("계속하기"));
		Add(TEXT("다시 시작"));
		Add(TEXT("설정"));
		Add(TEXT("타이틀로"));
		break;

	default:
		break;
	}
	return Items;
}
