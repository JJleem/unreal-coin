// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TraversalComponent.h"
#include "GameFeelComponent.generated.h"

class ACharacter;
class UCameraComponent;
class USoundBase;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;

/**
 *  Feedback that makes the character's moves feel physical, none of which changes the gameplay:
 *  speed-based field of view, camera shake on hard landings and impacts, a short hit stop when something breaks,
 *  footsteps, whooshes for rolls and slides, and a blob shadow on the scans (which can't receive real shadows)
 */
UCLASS(ClassGroup=(CoinDemo), meta=(BlueprintSpawnableComponent))
class UGameFeelComponent : public UActorComponent
{
	GENERATED_BODY()

protected:

	/** Field of view standing still and walking */
	UPROPERTY(EditAnywhere, Category="Feel|Camera")
	float BaseFOV = 90.0f;

	/** Extra field of view at full sprint, and during rolls and slides */
	UPROPERTY(EditAnywhere, Category="Feel|Camera")
	float SpeedFOV = 12.0f;

	/** Ground distance per footstep while walking and while sprinting */
	UPROPERTY(EditAnywhere, Category="Feel|Audio", meta = (Units = "cm"))
	float WalkStride = 150.0f;

	UPROPERTY(EditAnywhere, Category="Feel|Audio", meta = (Units = "cm"))
	float SprintStride = 210.0f;

	UPROPERTY(EditAnywhere, Category="Feel|Audio")
	TObjectPtr<USoundBase> StepSound;

	UPROPERTY(EditAnywhere, Category="Feel|Audio")
	TObjectPtr<USoundBase> LandSound;

	UPROPERTY(EditAnywhere, Category="Feel|Audio")
	TObjectPtr<USoundBase> WhooshSound;

	/** Soft dark disc projected under the character on scan stages */
	UPROPERTY(VisibleAnywhere, Category="Feel|Shadow")
	TObjectPtr<UStaticMeshComponent> BlobShadow;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> BlobShadowMaterial;

	/** Current camera shake strength, decaying to zero */
	float ShakeAmount = 0.0f;
	float ShakeTime = 0.0f;

	/** Real time (unaffected by time dilation) when the current hit stop ends, or 0 */
	double HitStopEnd = 0.0;

	/** Footprints (XY) of meshes tagged LitGround: real shadows fall there, so the blob shadow hides */
	TArray<FBox2D> LitGround;

	float StepDistance = 0.0f;
	ETraversalAction LastAction = ETraversalAction::None;

public:

	UGameFeelComponent();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Shakes the camera; 1 is a hard landing */
	void AddShake(float Amount);

	/** Freezes the game for a moment to sell an impact */
	void HitStop(float RealSeconds = 0.07f);

	/** Thud and shake scaled by how fast the character hit the ground */
	void OnLanded(float ImpactSpeed);

protected:

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	ACharacter* GetCharacter() const;
	UCameraComponent* GetCamera() const;

	void UpdateCamera(float DeltaTime);
	void UpdateFootsteps(float DeltaTime);
	void UpdateBlobShadow();
};
