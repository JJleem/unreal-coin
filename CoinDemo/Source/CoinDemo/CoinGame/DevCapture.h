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
 *    -Bot=fwd:2,jump,...  play a scripted input sequence on the player: fwd/back/left/right/coin/smash/collectall/wait/jump/land
 *                         or any parameterless character function (DoRoll, DoCrouch...), or a menu key
 *                         (MenuUp, MenuDown, MenuLeft, MenuRight, MenuConfirm, MenuBack), each optionally ":seconds"
 *    -StartAt=x,y,z,yaw   put the player here when play starts
 *    -LightScale=0.5      multiply the intensity of every light in the level
 *    -ExposureBias=1      switch post process volumes to manual exposure with this bias
 *    -Views=x,y,z,yaw,pitch;...  visit these camera views in turn and screenshot each (player placed at x,y,z), for
 *                         comparing render settings or scan versions from exactly the same cameras
 *    -Cvars=a=1;b=2       set console variables when play starts (and log the render settings that matter here)
 *    -NoHUD               hide the HUD, for clean comparison shots
 *    -HidePlayer          hide the player character (the camera still follows it)
 *    -QuitAfterShots      exit after the last screenshot
 *  Every screenshot also logs the average frame rate since the previous one.
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

	/** True while the current bot step walks toward the nearest coin, or the nearest breakable barrier */
	bool bSeekCoin = false;
	bool bSeekBarrier = false;

	/** Movement input applied every frame by the current bot step */
	FVector2D BotMove = FVector2D::ZeroVector;

	/** Number of screenshots taken */
	int32 ShotCount = 0;

	/** Character yaw when the bot started; bot movement and the camera angle are relative to it */
	TOptional<float> BaseYaw;

	/** -StartAt=x,y,z[,yaw]: where to put the player when play starts */
	TOptional<FTransform> StartTransform;

	/** Camera override from the command line */
	TOptional<float> ShotYaw;
	float ShotPitch = -10.0f;

	bool bQuitAfterShots = false;
	bool bHidePlayer = false;
	bool bNoHUD = false;

	/** -Views: player location, and camera yaw and pitch per view; the next one to visit */
	TArray<TPair<FVector, FRotator>> Views;
	int32 NextView = 0;
	TOptional<FRotator> HeldView;
	TArray<bool> FreeCamera;

	UPROPERTY(Transient)
	TObjectPtr<class ACameraActor> ViewCamera;
	float NextViewTime = 3.0f;

	/** Frames and real seconds since the last screenshot, for the frame rate log */
	int32 FrameCount = 0;
	double FrameTime = 0.0;
	double WorstFrame = 0.0;

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
