// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BreakableBarrier.generated.h"

class UMaterialInterface;
class USoundBase;
class UStaticMesh;

/**
 *  An invisible obstacle the player can smash by running, rolling or sliding into it
 *  Scan stages use these for small free-standing blobs (people, signs, noise) the wall detection blocked off.
 *  The boxes are drawn with the barrier material, which only shows up when the player is close.
 */
UCLASS()
class ABreakableBarrier : public AActor
{
	GENERATED_BODY()

protected:

	/** Blocking boxes in world space */
	UPROPERTY(EditAnywhere, Category="Barrier")
	TArray<FBox> Boxes;

	/** Material for the boxes, normally the proximity grid shared with the walls */
	UPROPERTY(EditAnywhere, Category="Barrier")
	TObjectPtr<UMaterialInterface> BarrierMaterial;

	UPROPERTY(EditAnywhere, Category="Barrier")
	TObjectPtr<USoundBase> SmashSound;

	/** Number of debris pieces thrown when smashed */
	UPROPERTY(EditAnywhere, Category="Barrier")
	int32 DebrisCount = 14;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> CubeMesh;

	bool bSmashed = false;

public:

	/** Constructor */
	ABreakableBarrier();

	/** Sets the blocking boxes, in world space */
	UFUNCTION(BlueprintCallable, Category="Barrier")
	void SetBoxes(const TArray<FBox>& InBoxes) { Boxes = InBoxes; }

	/** Breaks the barrier apart, throwing debris along Impulse */
	UFUNCTION(BlueprintCallable, Category="Barrier")
	void Smash(FVector Impulse);

protected:

	/** Builds a cube component per box */
	virtual void BeginPlay() override;
};
