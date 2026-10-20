// Copyright Epic Games, Inc. All Rights Reserved.


#include "BreakableBarrier.h"
#include "HoloStyle.h"
#include "CoinDemo.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

ABreakableBarrier::ABreakableBarrier()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Material(TEXT("/Game/Stages/Common/M_Barrier.M_Barrier"));
	static ConstructorHelpers::FObjectFinder<USoundBase> Sound(TEXT("/Game/Audio/SFX_Smash.SFX_Smash"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hologram(TEXT("/Game/CoinGame/Materials/M_Hologram.M_Hologram"));
	VisibleMaterial = Hologram.Object;
	CubeMesh = Cube.Object;
	BarrierMaterial = Material.Object;
	SmashSound = Sound.Object;
}

void ABreakableBarrier::BeginPlay()
{
	Super::BeginPlay();

	// the engine cube is 100 cm across and centred on its pivot
	for (const FBox& Box : Boxes)
	{
		UStaticMeshComponent* Part = NewObject<UStaticMeshComponent>(this);
		Part->SetStaticMesh(CubeMesh);
		Part->SetMaterial(0, bAlwaysVisible ? VisibleMaterial : BarrierMaterial);
		Part->SetCollisionProfileName(TEXT("BlockAll"));
		Part->SetCastShadow(false);
		Part->SetupAttachment(RootComponent);
		Part->SetWorldLocationAndRotation(Box.GetCenter(), FRotator::ZeroRotator);
		Part->SetWorldScale3D(Box.GetSize() / 100.0f);
		Part->RegisterComponent();

		if (bAlwaysVisible)
		{
			if (UMaterialInstanceDynamic* Material = Part->CreateDynamicMaterialInstance(0))
			{
				Material->SetVectorParameterValue(TEXT("Color"), FLinearColor(1.0f, 0.45f, 0.1f));
				Material->SetScalarParameterValue(TEXT("Fill"), 0.22f);
				Material->SetScalarParameterValue(TEXT("Intensity"), 2.0f * HoloStyle::GetIntensityScale(GetWorld()));
			}
		}
	}
}

FBox ABreakableBarrier::GetBounds() const
{
	FBox Bounds(ForceInit);
	for (const FBox& Box : Boxes)
	{
		Bounds += Box;
	}
	return Bounds;
}

void ABreakableBarrier::Smash(FVector Impulse)
{
	if (bSmashed)
	{
		return;
	}
	bSmashed = true;

	const FBox Bounds = GetBounds();

	if (SmashSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, SmashSound, Bounds.GetCenter());
	}

	// chunks fly off in the direction of the hit
	const FVector Direction = Impulse.GetSafeNormal();
	for (int32 i = 0; i < DebrisCount; ++i)
	{
		const FVector Location(
			FMath::RandRange(Bounds.Min.X, Bounds.Max.X),
			FMath::RandRange(Bounds.Min.Y, Bounds.Max.Y),
			FMath::RandRange(Bounds.Min.Z + 120.0f, FMath::Min(Bounds.Max.Z, Bounds.Min.Z + 260.0f)));

		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AStaticMeshActor* Chunk = GetWorld()->SpawnActor<AStaticMeshActor>(Location, FRotator(FMath::FRand() * 360.0f, FMath::FRand() * 360.0f, 0.0f), Params);
		if (!Chunk)
		{
			continue;
		}

		UStaticMeshComponent* Mesh = Chunk->GetStaticMeshComponent();
		Mesh->SetMobility(EComponentMobility::Movable);
		Mesh->SetStaticMesh(CubeMesh);
		Mesh->SetWorldScale3D(FVector(FMath::RandRange(0.08f, 0.22f)));
		if (UMaterialInstanceDynamic* Material = Mesh->CreateDynamicMaterialInstance(0, CubeMesh->GetMaterial(0)))
		{
			Material->SetVectorParameterValue(TEXT("Color"), bAlwaysVisible ? FLinearColor(1.0f, 0.5f, 0.15f) : FLinearColor(0.55f, 0.85f, 1.0f));
		}
		Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));
		Mesh->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
		Mesh->SetSimulatePhysics(true);
		Mesh->AddImpulse((Direction * 500.0f + FMath::VRand() * 250.0f + FVector(0.0f, 0.0f, 300.0f)), NAME_None, true);
		Chunk->SetLifeSpan(2.5f);
	}

	UE_LOG(LogCoinDemo, Log, TEXT("Smashed %s"), *GetName());
	Destroy();
}
