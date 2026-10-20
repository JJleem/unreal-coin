// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "JumpPad.generated.h"

class UBoxComponent;
class UStaticMeshComponent;
class USoundBase;

/**
 *  A glowing pad that throws the player in an arc onto a target, usually a floating platform
 *  A thin light column above it makes it easy to spot across a scan.
 */
UCLASS()
class AJumpPad : public AActor
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UBoxComponent* Trigger;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UStaticMeshComponent* Pad;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UStaticMeshComponent* Beam;

protected:

	/** Where the arc lands, in world space */
	UPROPERTY(EditAnywhere, Category="Jump Pad", meta = (MakeEditWidget))
	FVector Target = FVector(0.0f, 0.0f, 600.0f);

	/** How far above the higher of the pad and the target the arc peaks */
	UPROPERTY(EditAnywhere, Category="Jump Pad", meta = (Units = "cm"))
	float ArcHeight = 250.0f;

	UPROPERTY(EditAnywhere, Category="Jump Pad")
	FLinearColor Color = FLinearColor(0.2f, 1.0f, 0.55f);

	UPROPERTY(EditAnywhere, Category="Jump Pad")
	TObjectPtr<USoundBase> LaunchSound;

	/** Hologram brightness for this stage's exposure */
	float IntensityScale = 1.0f;

	/** World time of the last launch, for the pulse */
	float LastLaunchTime = -100.0f;

	UPROPERTY(Transient)
	TObjectPtr<class UMaterialInstanceDynamic> PadMaterial;

public:

	AJumpPad();

	virtual void Tick(float DeltaTime) override;

	/** Sets the landing point in world space */
	UFUNCTION(BlueprintCallable, Category="Jump Pad")
	void SetTarget(FVector InTarget) { Target = InTarget; }

protected:

	virtual void BeginPlay() override;

	UFUNCTION()
	void BeginOverlap(AActor* OverlappedActor, AActor* OtherActor);
};
