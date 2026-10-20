// Copyright Epic Games, Inc. All Rights Reserved.


#include "HoloPlatform.h"
#include "HoloStyle.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AHoloPlatform::AHoloPlatform()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hologram(TEXT("/Game/CoinGame/Materials/M_Hologram.M_Hologram"));
	Mesh->SetStaticMesh(Cube.Object);
	Mesh->SetMaterial(0, Hologram.Object);
	Mesh->SetCollisionProfileName(TEXT("BlockAll"));
	Mesh->SetCastShadow(false);
	Mesh->SetMobility(EComponentMobility::Movable);
}

void AHoloPlatform::SetLook(FVector InSize, FLinearColor InColor)
{
	Size = InSize;
	Color = InColor;
	Mesh->SetWorldScale3D(Size / 100.0f);
}

void AHoloPlatform::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	// the engine cube is 100 cm across, centred on its pivot
	Mesh->SetWorldScale3D(Size / 100.0f);
}

void AHoloPlatform::BeginPlay()
{
	Super::BeginPlay();

	if (UMaterialInstanceDynamic* Material = Mesh->CreateDynamicMaterialInstance(0))
	{
		Material->SetVectorParameterValue(TEXT("Color"), Color);
		Material->SetScalarParameterValue(TEXT("Fill"), 0.18f);
		Material->SetScalarParameterValue(TEXT("Intensity"), 2.0f * HoloStyle::GetIntensityScale(GetWorld()));
	}

	HomeLocation = GetActorLocation();
	SetActorTickEnabled(!MoveOffset.IsNearlyZero());
}

void AHoloPlatform::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	// ease in and out at both ends
	const float Phase = GetWorld()->GetTimeSeconds() / FMath::Max(MovePeriod, 0.1f) * UE_TWO_PI;
	SetActorLocation(HomeLocation + MoveOffset * (0.5f - 0.5f * FMath::Cos(Phase)));
}
