// Copyright Epic Games, Inc. All Rights Reserved.


#include "DevCapture.h"
#include "CoinDemo.h"
#include "CoinDemoCharacter.h"
#include "CoinPickup.h"
#include "BreakableBarrier.h"
#include "CoinDemoGameMode.h"
#include "GameMenuComponent.h"
#include "EngineUtils.h"
#include "Components/LightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformMisc.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
#include "GameFramework/HUD.h"
#include "Misc/App.h"
#include "HAL/IConsoleManager.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Containers/Ticker.h"

UDevCapture::UDevCapture()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
	PrimaryComponentTick.bTickEvenWhenPaused = true;
}

void UDevCapture::BeginPlay()
{
	Super::BeginPlay();

	const TCHAR* CommandLine = FCommandLine::Get();

	FString Times;
	if (FParse::Value(CommandLine, TEXT("ShotAt="), Times, false))
	{
		TArray<FString> Parts;
		Times.ParseIntoArray(Parts, TEXT(","));
		for (const FString& Part : Parts)
		{
			ShotTimes.Add(FCString::Atof(*Part));
		}
		ShotTimes.Sort();
	}

	FParse::Value(CommandLine, TEXT("ShotName="), ShotName);
	if (ShotName.IsEmpty())
	{
		ShotName = UGameplayStatics::GetCurrentLevelName(this, true);
	}

	float Yaw = 0.0f;
	if (FParse::Value(CommandLine, TEXT("ShotYaw="), Yaw))
	{
		ShotYaw = Yaw;
	}
	FParse::Value(CommandLine, TEXT("ShotPitch="), ShotPitch);
	bQuitAfterShots = FParse::Param(CommandLine, TEXT("QuitAfterShots"));
	bHidePlayer = FParse::Param(CommandLine, TEXT("HidePlayer"));
	bNoHUD = FParse::Param(CommandLine, TEXT("NoHUD"));

	FString Cvars;
	if (FParse::Value(CommandLine, TEXT("Cvars="), Cvars, false))
	{
		TArray<FString> Entries;
		Cvars.ParseIntoArray(Entries, TEXT(";"));
		for (const FString& Entry : Entries)
		{
			FString Name, Value;
			if (Entry.Split(TEXT("="), &Name, &Value))
			{
				if (IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(*Name))
				{
					Variable->Set(*Value, ECVF_SetByConsole);
				}
				else
				{
					UE_LOG(LogCoinDemo, Warning, TEXT("Cvars: no console variable %s"), *Name);
				}
			}
		}
	}
	if (ShotTimes.Num() > 0 || Views.Num() > 0 || !Cvars.IsEmpty())
	{
		for (const TCHAR* Name : { TEXT("r.ScreenPercentage"), TEXT("r.AntiAliasingMethod"), TEXT("gs.DebugForceLODLevel"), TEXT("r.Tonemapper.Sharpen") })
		{
			if (const IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(Name))
			{
				UE_LOG(LogCoinDemo, Log, TEXT("Render setting %s = %s"), Name, *Variable->GetString());
			}
		}
	}

	// each view: move there, give the camera two seconds to settle, then shoot
	FString ViewList;
	if (FParse::Value(CommandLine, TEXT("Views="), ViewList, false))
	{
		TArray<FString> Entries;
		ViewList.ParseIntoArray(Entries, TEXT(";"));
		for (const FString& Entry : Entries)
		{
			TArray<FString> Parts;
			Entry.ParseIntoArray(Parts, TEXT(","));
			if (Parts.Num() >= 5)
			{
				Views.Add({ FVector(FCString::Atof(*Parts[0]), FCString::Atof(*Parts[1]), FCString::Atof(*Parts[2])),
					FRotator(FCString::Atof(*Parts[4]), FCString::Atof(*Parts[3]), 0.0f) });
			}
		}
	}

	FString Start;
	if (FParse::Value(CommandLine, TEXT("StartAt="), Start, false))
	{
		TArray<FString> Parts;
		Start.ParseIntoArray(Parts, TEXT(","));
		if (Parts.Num() >= 3)
		{
			StartTransform = FTransform(FRotator(0.0f, Parts.Num() > 3 ? FCString::Atof(*Parts[3]) : 0.0f, 0.0f),
				FVector(FCString::Atof(*Parts[0]), FCString::Atof(*Parts[1]), FCString::Atof(*Parts[2])));
		}
	}

	FString Bot;
	if (FParse::Value(CommandLine, TEXT("Bot="), Bot, false))
	{
		Bot.ParseIntoArray(BotSteps, TEXT(","));
	}

	// scale every light in the level, to try lighting values without rebuilding the stages
	float LightScale = 1.0f;
	if (FParse::Value(CommandLine, TEXT("LightScale="), LightScale))
	{
		for (TObjectIterator<ULightComponentBase> It; It; ++It)
		{
			if (It->GetWorld() != GetWorld())
			{
				continue;
			}
			if (ULightComponent* Light = Cast<ULightComponent>(*It))
			{
				Light->SetIntensity(Light->Intensity * LightScale);
			}
			else if (USkyLightComponent* Sky = Cast<USkyLightComponent>(*It))
			{
				Sky->SetIntensity(Sky->Intensity * LightScale);
			}
		}
	}

	// fixed manual exposure instead of eye adaptation
	float ExposureBias = 0.0f;
	if (FParse::Value(CommandLine, TEXT("ExposureBias="), ExposureBias))
	{
		for (TActorIterator<APostProcessVolume> It(GetWorld()); It; ++It)
		{
			FPostProcessSettings& Settings = It->Settings;
			Settings.bOverride_AutoExposureMethod = true;
			Settings.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
			Settings.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
			Settings.AutoExposureApplyPhysicalCameraExposure = false;
			Settings.bOverride_AutoExposureBias = true;
			Settings.AutoExposureBias = ExposureBias;
		}
	}

	SetComponentTickEnabled(ShotTimes.Num() > 0 || Views.Num() > 0 || BotSteps.Num() > 0 || StartTransform.IsSet() || bNoHUD || bHidePlayer);
}

void UDevCapture::RunBotStep()
{
	BotMove = FVector2D::ZeroVector;
	if (!BotSteps.IsValidIndex(BotStep))
	{
		return;
	}

	// "action" or "action:seconds"
	FString Action = BotSteps[BotStep++], Seconds;
	Action.Split(TEXT(":"), &Action, &Seconds);
	BotStepTime = Seconds.IsEmpty() ? 0.5f : FCString::Atof(*Seconds);

	// menu keys work without a character, e.g. on the title screen
	if (Action.StartsWith(TEXT("Menu")))
	{
		const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
		if (UGameMenuComponent* Menu = PC ? PC->FindComponentByClass<UGameMenuComponent>() : nullptr)
		{
			UE_LOG(LogCoinDemo, Log, TEXT("Bot: %s"), *Action);
			Menu->RunCommand(Action.RightChop(4));
		}
		return;
	}

	ACoinDemoCharacter* Character = Cast<ACoinDemoCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));
	if (!Character)
	{
		return;
	}

	UE_LOG(LogCoinDemo, Log, TEXT("Bot: %s for %.1fs at %s"), *Action, BotStepTime, *Character->GetActorLocation().ToCompactString());

	bSeekCoin = Action == TEXT("coin");
	bSeekBarrier = Action == TEXT("smash");
	if (bSeekCoin || bSeekBarrier) {}
	else if (Action == TEXT("fwd")) { BotMove = FVector2D(0, 1); }
	else if (Action == TEXT("back")) { BotMove = FVector2D(0, -1); }
	else if (Action == TEXT("left")) { BotMove = FVector2D(-1, 0); }
	else if (Action == TEXT("right")) { BotMove = FVector2D(1, 0); }
	else if (Action == TEXT("jump")) { Character->DoJumpStart(); }
	else if (Action == TEXT("collectall"))
	{
		// cheat for checking the clear flow: every remaining coin counts as collected
		if (ACoinDemoGameMode* GM = GetWorld()->GetAuthGameMode<ACoinDemoGameMode>())
		{
			for (TActorIterator<ACoinPickup> It(GetWorld()); It; ++It)
			{
				if (It->GetActorEnableCollision())
				{
					It->SetActorEnableCollision(false);
					It->Destroy();
					GM->CoinCollected();
				}
			}
		}
	}
	else if (Action == TEXT("land")) { Character->DoJumpEnd(); }
	else if (Action != TEXT("wait"))
	{
		// any other step calls a parameterless function on the character, e.g. "DoRoll"
		if (UFunction* Function = Character->FindFunction(*Action))
		{
			if (Function->ParmsSize == 0)
			{
				Character->ProcessEvent(Function, nullptr);
			}
		}
		else
		{
			UE_LOG(LogCoinDemo, Warning, TEXT("Bot: no function %s on %s"), *Action, *Character->GetName());
		}
	}
}

void UDevCapture::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	// real time, so screenshots of the pause menu still happen
	const float Now = GetWorld()->GetRealTimeSeconds();
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	ACoinDemoCharacter* Character = Cast<ACoinDemoCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));

	// frame rate since the last screenshot; the first second after loading is skipped
	if (Now > 1.0f)
	{
		const double Delta = FApp::GetDeltaTime();
		++FrameCount;
		FrameTime += Delta;
		WorstFrame = FMath::Max(WorstFrame, Delta);
	}

	if (bNoHUD && PC && PC->GetHUD())
	{
		PC->GetHUD()->bShowHUD = false;
	}

	if (Views.IsValidIndex(NextView) && Now >= NextViewTime && Character && PC)
	{
		const TPair<FVector, FRotator>& View = Views[NextView++];
		HeldView = View.Value;
		Character->TeleportTo(View.Key, FRotator(0.0f, View.Value.Yaw, 0.0f), false, true);
		Character->GetCharacterMovement()->StopMovementImmediately();
		PC->SetControlRotation(View.Value);
		// the shot follows its teleport, so a slow start can't shift shots onto the wrong view
		ShotTimes.Add(Now + 2.0f);
		ShotTimes.Sort();
		NextViewTime = Now + 3.0f;
	}

	// hold the view's camera angle against anything that turns the controller while settling
	if (HeldView.IsSet() && PC)
	{
		PC->SetControlRotation(HeldView.GetValue());
	}

	if (bHidePlayer && Character)
	{
		Character->SetActorHiddenInGame(true);
		for (UActorComponent* Component : Character->GetComponents())
		{
			if (USceneComponent* Scene = Cast<USceneComponent>(Component))
			{
				Scene->SetHiddenInGame(true, true);
			}
		}
	}

	// move the player to the requested start once it exists
	if (StartTransform.IsSet() && Character && PC)
	{
		Character->TeleportTo(StartTransform->GetLocation(), StartTransform->Rotator());
		PC->SetControlRotation(StartTransform->Rotator());
		BaseYaw = StartTransform->Rotator().Yaw;
		StartTransform.Reset();
	}

	// scripted input; menu steps run before there is a character
	if (BotSteps.Num() > 0 && !Character)
	{
		BotStepTime -= DeltaTime;
		if (BotStepTime <= 0.0f)
		{
			RunBotStep();
		}
	}
	else if (BotSteps.Num() > 0 && Character)
	{
		BotStepTime -= DeltaTime;
		if (BotStepTime <= 0.0f)
		{
			RunBotStep();
		}
		if (!BaseYaw.IsSet())
		{
			BaseYaw = Character->GetActorRotation().Yaw;
		}
		if (bSeekCoin || bSeekBarrier)
		{
			// walk straight at the nearest coin still up for grabs, or the nearest breakable barrier
			const AActor* Nearest = nullptr;
			FVector Target = FVector::ZeroVector;
			float NearestDistance = TNumericLimits<float>::Max();
			auto Consider = [&](const AActor* Actor, const FVector& Location)
			{
				const float Distance = FVector::DistSquared2D(Location, Character->GetActorLocation());
				if (Distance < NearestDistance)
				{
					Nearest = Actor;
					Target = Location;
					NearestDistance = Distance;
				}
			};
			if (bSeekCoin)
			{
				for (TActorIterator<ACoinPickup> It(GetWorld()); It; ++It)
				{
					if (It->GetActorEnableCollision())
					{
						Consider(*It, It->GetActorLocation());
					}
				}
			}
			else
			{
				for (TActorIterator<ABreakableBarrier> It(GetWorld()); It; ++It)
				{
					Consider(*It, It->GetComponentsBoundingBox().GetCenter());
				}
			}
			if (Nearest)
			{
				Character->AddMovementInput((Target - Character->GetActorLocation()).GetSafeNormal2D());
			}
		}
		else if (!BotMove.IsZero())
		{
			// fixed world directions, so turning the camera for screenshots doesn't steer the bot
			const FRotator Base(0.0f, BaseYaw.GetValue(), 0.0f);
			Character->AddMovementInput(FRotationMatrix(Base).GetUnitAxis(EAxis::X), BotMove.Y);
			Character->AddMovementInput(FRotationMatrix(Base).GetUnitAxis(EAxis::Y), BotMove.X);
		}
	}

	// hold the camera at the requested angle around the player
	if (ShotYaw.IsSet() && PC && Character && ShotTimes.Num() > 0)
	{
		const float Yaw = BaseYaw.IsSet() ? BaseYaw.GetValue() : Character->GetActorRotation().Yaw;
		PC->SetControlRotation(FRotator(ShotPitch, Yaw + ShotYaw.GetValue(), 0.0f));
	}

	if (ShotTimes.Num() > 0 && Now >= ShotTimes[0])
	{
		ShotTimes.RemoveAt(0);
		const FString File = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("Screenshots") / FString::Printf(TEXT("%s_%02d.png"), *ShotName, ++ShotCount));
		FScreenshotRequest::RequestScreenshot(File, true, false);
		UE_LOG(LogCoinDemo, Log, TEXT("Screenshot %s at %.1fs, player at %s, %.0f fps average (worst frame %.1f ms)"), *File, Now,
			Character ? *Character->GetActorLocation().ToCompactString() : TEXT("-"), FrameTime > 0.0 ? FrameCount / FrameTime : 0.0, WorstFrame * 1000.0);
		FrameCount = 0;
		FrameTime = 0.0;
		WorstFrame = 0.0;

		if (ShotTimes.Num() == 0 && !Views.IsValidIndex(NextView) && bQuitAfterShots)
		{
			// a core ticker, so it also fires while the game is paused
			FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float) { FPlatformMisc::RequestExit(false, TEXT("DevCapture")); return false; }), 1.5f);
		}
	}
}
