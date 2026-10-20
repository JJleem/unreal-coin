// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GemPickup.generated.h"

class USphereComponent;
class UStaticMeshComponent;
class USoundBase;

/**
 *  The hidden gem of a stage: optional, hard to reach, and remembered in the save once found
 *  Doesn't count towards the coins. A gem found in an earlier run is drawn faded but can still be picked up.
 */
UCLASS()
class AGemPickup : public AActor
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	USphereComponent* Sphere;

	/** Two cones tip to tip make an octahedron */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UStaticMeshComponent* Top;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UStaticMeshComponent* Bottom;

protected:

	UPROPERTY(EditAnywhere, Category="Gem")
	FLinearColor Color = FLinearColor(1.0f, 0.25f, 0.85f);

	UPROPERTY(EditAnywhere, Category="Gem")
	TObjectPtr<USoundBase> CollectSound;

	/** Seconds since collection, or a negative value while waiting */
	float CollectedTime = -1.0f;

public:

	AGemPickup();

	virtual void Tick(float DeltaTime) override;

protected:

	virtual void BeginPlay() override;

	UFUNCTION()
	void BeginOverlap(AActor* OverlappedActor, AActor* OtherActor);
};
