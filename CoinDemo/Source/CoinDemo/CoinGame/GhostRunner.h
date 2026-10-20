// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "CoinDemoSaveGame.h"
#include "GhostRunner.generated.h"

/**
 *  Movement for the ghost: doesn't simulate anything, it only reports the velocity and acceleration of the
 *  recorded path so the regular locomotion anim blueprint animates it
 */
UCLASS()
class UGhostMovementComponent : public UCharacterMovementComponent
{
	GENERATED_BODY()

public:

	void SetReplayState(const FVector& InVelocity, bool bFalling)
	{
		Velocity = InVelocity;
		Acceleration = InVelocity.Size2D() > 10.0f ? InVelocity.GetSafeNormal2D() * GetMaxAcceleration() : FVector::ZeroVector;
		MovementMode = bFalling ? MOVE_Falling : MOVE_Walking;
	}
};

/**
 *  A translucent mannequin replaying the player's best run of the stage
 */
UCLASS()
class AGhostRunner : public ACharacter
{
	GENERATED_BODY()

	FGhostTrack Track;

	/** World time the replay started */
	float StartTime = 0.0f;

public:

	AGhostRunner(const FObjectInitializer& ObjectInitializer);

	virtual void Tick(float DeltaTime) override;

	/** Starts replaying Track from InStartTime (world time) */
	void Play(const FGhostTrack& InTrack, float InStartTime);

protected:

	virtual void BeginPlay() override;
};
