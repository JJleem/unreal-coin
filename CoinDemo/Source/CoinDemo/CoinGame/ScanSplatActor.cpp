// Copyright Epic Games, Inc. All Rights Reserved.


#include "ScanSplatActor.h"
#include "NanoGSGaussianSplatComponent.h"
#include "Misc/CommandLine.h"

AScanSplatActor::AScanSplatActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Splat = CreateDefaultSubobject<UGaussianSplatComponent>(TEXT("Splat"));
	RootComponent = Splat;

	// the scan is a backdrop, collision comes from the ground mesh
	Splat->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AScanSplatActor::BeginPlay()
{
	Super::BeginPlay();

	float LODError = 0.0f;
	if (FParse::Value(FCommandLine::Get(), TEXT("SplatLOD="), LODError))
	{
		Splat->SetNanitePrecision(LODError);
	}

	int32 SHOrder = 0;
	if (FParse::Value(FCommandLine::Get(), TEXT("SplatSH="), SHOrder))
	{
		Splat->SHOrder = SHOrder;
		// the component hides its own override; the base one recreates the render proxy with the new order
		static_cast<UActorComponent*>(Splat)->MarkRenderStateDirty();
	}
}
