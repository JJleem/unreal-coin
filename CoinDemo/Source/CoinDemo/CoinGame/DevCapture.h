// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "DevCapture.generated.h"

/**
 *  Development helper for unattended checks, driven by the command line:
 *    -ShotAt=10,14,18     take a screenshot at each of these times (seconds after BeginPlay)
 *    -ShotName=stage1     file name prefix, written to Saved/Screenshots/<platform>/
 *    -ShotYaw=180         rotate the camera around the player before the first shot (180 = look at the face)
 *    -ShotPitch=-10       camera pitch for the shots
 *    -Bot=run,jump,...    play a scripted input sequence on the player, see UDevCapture::RunBotStep
 *    -QuitAfterShots      exit after the last screenshot
 *  Does nothing without those arguments, so it is safe to leave on the GameMode.
 */
UCLASS(ClassGroup=(CoinDemo))
class UDevCapture : public UActorComponent
{
	GENERATED_BODY()

	/** Remaining screenshot times */
	TArray<float> ShotTimes;

	/** Screenshot file name prefix */
	FString ShotName;

	/** Scripted bot steps, each "action" or "action:seconds" */
	TArray<FString> BotSteps;

	/** Index of the next bot step */
	int32 BotStep = 0;

	/** Time left in the current bot step */
	float BotStepTime = 0.0f;

	/** Movement input applied every frame by the current bot step */
	FVector2D BotMove = FVector2D::ZeroVector;

	/** Number of screenshots taken */
	int32 ShotCount = 0;

	/** Camera override from the command line */
	TOptional<float> ShotYaw;
	float ShotPitch = -10.0f;

	bool bQuitAfterShots = false;

public:

	/** Constructor */
	UDevCapture();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

protected:

	/** Reads the command line */
	virtual void BeginPlay() override;

	/** Starts the next scripted bot step */
	void RunBotStep();
};
