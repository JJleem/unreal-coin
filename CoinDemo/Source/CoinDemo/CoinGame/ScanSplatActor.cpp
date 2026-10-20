// Copyright Epic Games, Inc. All Rights Reserved.


#include "ScanSplatActor.h"
#include "NanoGSGaussianSplatComponent.h"
#include "GaussianSplatAsset.h"
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

	// -SplatAsset=/Game/...: render another import of the scan, to compare cleaned versions in place
	FString AssetPath;
	if (FParse::Value(FCommandLine::Get(), TEXT("SplatAsset="), AssetPath))
	{
		if (UGaussianSplatAsset* Asset = LoadObject<UGaussianSplatAsset>(nullptr, *AssetPath))
		{
			Splat->SetSplatAsset(Asset);
		}
		else
		{
			UE_LOG(LogTemp, Warning, TEXT("SplatAsset %s not found"), *AssetPath);
		}
	}

	float Opacity = 0.0f;
	if (FParse::Value(FCommandLine::Get(), TEXT("SplatOpacity="), Opacity))
	{
		Splat->OpacityScale = Opacity;
		static_cast<UActorComponent*>(Splat)->MarkRenderStateDirty();
	}

	float Scale = 0.0f;
	if (FParse::Value(FCommandLine::Get(), TEXT("SplatScale="), Scale))
	{
		Splat->SplatScale = Scale;
		static_cast<UActorComponent*>(Splat)->MarkRenderStateDirty();
	}

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
