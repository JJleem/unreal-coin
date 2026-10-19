// Copyright Epic Games, Inc. All Rights Reserved.


#include "DevCapture.h"
#include "CoinDemo.h"
#include "CoinDemoCharacter.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformMisc.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

UDevCapture::UDevCapture()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
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

	FString Bot;
	if (FParse::Value(CommandLine, TEXT("Bot="), Bot, false))
	{
		Bot.ParseIntoArray(BotSteps, TEXT(","));
	}

	SetComponentTickEnabled(ShotTimes.Num() > 0 || BotSteps.Num() > 0);
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

	ACoinDemoCharacter* Character = Cast<ACoinDemoCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));
	if (!Character)
	{
		return;
	}

	UE_LOG(LogCoinDemo, Log, TEXT("Bot: %s for %.1fs at %s"), *Action, BotStepTime, *Character->GetActorLocation().ToCompactString());

	if (Action == TEXT("fwd")) { BotMove = FVector2D(0, 1); }
	else if (Action == TEXT("back")) { BotMove = FVector2D(0, -1); }
	else if (Action == TEXT("left")) { BotMove = FVector2D(-1, 0); }
	else if (Action == TEXT("right")) { BotMove = FVector2D(1, 0); }
	else if (Action == TEXT("jump")) { Character->DoJumpStart(); }
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

	const float Now = GetWorld()->GetTimeSeconds();
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	ACoinDemoCharacter* Character = Cast<ACoinDemoCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));

	// scripted input
	if (BotSteps.Num() > 0 && Character)
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
		if (!BotMove.IsZero())
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
		UE_LOG(LogCoinDemo, Log, TEXT("Screenshot %s at %.1fs, player at %s"), *File, Now, Character ? *Character->GetActorLocation().ToCompactString() : TEXT("-"));

		if (ShotTimes.Num() == 0 && bQuitAfterShots)
		{
			FTimerHandle Quit;
			GetWorld()->GetTimerManager().SetTimer(Quit, [] { FPlatformMisc::RequestExit(false, TEXT("DevCapture")); }, 1.5f, false);
		}
	}
}
