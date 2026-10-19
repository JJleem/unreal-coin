// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ScanSplatActor.generated.h"

class UGaussianSplatComponent;

/**
 *  A placeable actor that renders an ANNX Gaussian Splatting scan as a stage backdrop
 *  The splat is visual only; walkable ground comes from a separate collision mesh
 */
UCLASS()
class AScanSplatActor : public AActor
{
	GENERATED_BODY()

	/** Renders the Gaussian splats */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UGaussianSplatComponent* Splat;

public:

	/** Constructor */
	AScanSplatActor();

	/** Applies -SplatLOD=<error threshold> and -SplatSH=<order> from the command line, for quick quality comparisons */
	virtual void BeginPlay() override;

	/** Returns the splat component */
	UFUNCTION(BlueprintPure, Category="Scan")
	UGaussianSplatComponent* GetSplat() const { return Splat; }
};
