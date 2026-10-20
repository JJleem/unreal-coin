// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CoinPickup.generated.h"

class USphereComponent;
class UStaticMeshComponent;
class USoundBase;

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

	/** Played where the coin is collected */
	UPROPERTY(EditAnywhere, Category="Coin")
	TObjectPtr<USoundBase> CollectSound;

	/** Length of the fly-up-and-vanish animation after collection */
	UPROPERTY(EditAnywhere, Category="Coin", meta = (Units = "s"))
	float CollectDuration = 0.45f;

	/** Seconds since collection, or a negative value while the coin is waiting */
	float CollectedTime = -1.0f;

	/** The coin flies to a player who comes this close */
	UPROPERTY(EditAnywhere, Category="Coin", meta = (Units = "cm"))
	float MagnetRadius = 320.0f;

	/** Speed while flying to the player, 0 until the magnet catches it */
	float MagnetSpeed = 0.0f;

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
