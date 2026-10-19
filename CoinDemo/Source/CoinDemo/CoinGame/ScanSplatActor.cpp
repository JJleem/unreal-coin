// Copyright Epic Games, Inc. All Rights Reserved.


#include "ScanSplatActor.h"
#include "NanoGSGaussianSplatComponent.h"

AScanSplatActor::AScanSplatActor()
{
	PrimaryActorTick.bCanEverTick = false;

	Splat = CreateDefaultSubobject<UGaussianSplatComponent>(TEXT("Splat"));
	RootComponent = Splat;

	// the scan is a backdrop, collision comes from the ground mesh
	Splat->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}
