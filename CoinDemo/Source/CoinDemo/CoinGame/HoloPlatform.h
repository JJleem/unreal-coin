// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HoloPlatform.generated.h"

class UStaticMeshComponent;

/**
 *  A glowing holographic block the player can stand on, part of the course laid over the scans
 *  Optionally drifts back and forth; the character rides along through its movement base.
 */
UCLASS()
class AHoloPlatform : public AActor
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UStaticMeshComponent* Mesh;

protected:

	/** Size of the block, in cm */
	UPROPERTY(EditAnywhere, Category="Platform")
	FVector Size = FVector(200.0f, 200.0f, 30.0f);

	UPROPERTY(EditAnywhere, Category="Platform")
	FLinearColor Color = FLinearColor(0.15f, 0.7f, 1.0f);

	/** World offset of the far end of the drift, zero for a platform that stays put */
	UPROPERTY(EditAnywhere, Category="Platform")
	FVector MoveOffset = FVector::ZeroVector;

	/** Seconds for a full trip there and back */
	UPROPERTY(EditAnywhere, Category="Platform", meta = (Units = "s"))
	float MovePeriod = 6.0f;

	FVector HomeLocation = FVector::ZeroVector;

public:

	AHoloPlatform();

	virtual void Tick(float DeltaTime) override;

	/** Sets the block size in cm and its color */
	UFUNCTION(BlueprintCallable, Category="Platform")
	void SetLook(FVector InSize, FLinearColor InColor);

	/** Makes the platform drift between its location and location + Offset */
	UFUNCTION(BlueprintCallable, Category="Platform")
	void SetMovement(FVector Offset, float Period) { MoveOffset = Offset; MovePeriod = Period; }

protected:

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
};
