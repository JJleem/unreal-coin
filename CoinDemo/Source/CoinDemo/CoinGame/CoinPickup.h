// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CoinPickup.generated.h"

class USphereComponent;
class UStaticMeshComponent;

/**
 *  A spinning coin that the player collects by touching it
 *  Reports to the GameMode, which advances to the next stage once every coin is collected
 */
UCLASS()
class ACoinPickup : public AActor
{
	GENERATED_BODY()

	/** Pickup bounding sphere */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	USphereComponent* Sphere;

	/** Visible coin mesh */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UStaticMeshComponent* Mesh;

protected:

	/** Spin speed in degrees per second */
	UPROPERTY(EditAnywhere, Category="Coin")
	float RotationSpeed = 180.0f;

	/** How far the coin floats up and down, in cm */
	UPROPERTY(EditAnywhere, Category="Coin")
	float BobHeight = 15.0f;

	/** Float cycles per second */
	UPROPERTY(EditAnywhere, Category="Coin")
	float BobSpeed = 0.5f;

	/** Color applied to the coin mesh */
	UPROPERTY(EditAnywhere, Category="Coin")
	FLinearColor CoinColor = FLinearColor(1.0f, 0.7f, 0.05f);

public:

	/** Constructor */
	ACoinPickup();

	/** Spins the coin every frame */
	virtual void Tick(float DeltaTime) override;

protected:

	/** Applies the coin color, also in the editor viewport */
	virtual void OnConstruction(const FTransform& Transform) override;

	/** Handles pickup collision */
	UFUNCTION()
	void BeginOverlap(AActor* OverlappedActor, AActor* OtherActor);

	/** Passes control to BP to play effects on pickup */
	UFUNCTION(BlueprintImplementableEvent, Category="Coin", meta = (DisplayName = "On Collected"))
	void BP_OnCollected();
};
