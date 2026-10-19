// Copyright Epic Games, Inc. All Rights Reserved.


#include "CoinPickup.h"
#include "CoinDemoGameMode.h"
#include "CoinDemo.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

ACoinPickup::ACoinPickup()
{
	PrimaryActorTick.bCanEverTick = true;

	// create the bounding sphere as the root
	Sphere = CreateDefaultSubobject<USphereComponent>(TEXT("Collision"));
	RootComponent = Sphere;

	Sphere->SetSphereRadius(60.0f);

	Sphere->SetCollisionObjectType(ECC_WorldDynamic);
	Sphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Sphere->SetCollisionResponseToAllChannels(ECR_Ignore);
	Sphere->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);

	// create the coin mesh: a flattened engine cylinder standing on its edge
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(RootComponent);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetRelativeRotation(FRotator(0.0f, 0.0f, 90.0f));
	Mesh->SetRelativeScale3D(FVector(0.6f, 0.6f, 0.08f));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (CylinderMesh.Succeeded())
	{
		Mesh->SetStaticMesh(CylinderMesh.Object);
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> ShapeMaterial(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (ShapeMaterial.Succeeded())
	{
		Mesh->SetMaterial(0, ShapeMaterial.Object);
	}

	static ConstructorHelpers::FObjectFinder<USoundBase> Chime(TEXT("/Game/Audio/SFX_Coin.SFX_Coin"));
	CollectSound = Chime.Object;

	// add the overlap handler
	OnActorBeginOverlap.AddDynamic(this, &ACoinPickup::BeginOverlap);
}

void ACoinPickup::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	// tint the basic shape material
	if (UMaterialInstanceDynamic* Material = Mesh->CreateDynamicMaterialInstance(0))
	{
		Material->SetVectorParameterValue(TEXT("Color"), CoinColor);
	}
}

void ACoinPickup::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	// collected: spin fast, pop up and shrink away
	if (CollectedTime >= 0.0f)
	{
		CollectedTime += DeltaTime;
		const float Alpha = FMath::Clamp(CollectedTime / CollectDuration, 0.0f, 1.0f);
		AddActorLocalRotation(FRotator(0.0f, RotationSpeed * 6.0f * DeltaTime, 0.0f));
		Mesh->SetRelativeLocation(FVector(0.0f, 0.0f, 120.0f * FMath::Sin(Alpha * UE_HALF_PI)));
		Mesh->SetRelativeScale3D(FVector(0.6f, 0.6f, 0.08f) * FMath::Lerp(1.4f, 0.0f, Alpha * Alpha));
		if (Alpha >= 1.0f)
		{
			Destroy();
		}
		return;
	}

	// spin around the vertical axis, scaled by frame time so the speed is frame rate independent
	AddActorLocalRotation(FRotator(0.0f, RotationSpeed * DeltaTime, 0.0f));

	// float up and down; the phase comes from the position so neighbouring coins don't move in lockstep
	const float Phase = GetActorLocation().X * 0.01f + GetActorLocation().Y * 0.013f;
	const float Time = GetWorld()->GetTimeSeconds();
	Mesh->SetRelativeLocation(FVector(0.0f, 0.0f, BobHeight * FMath::Sin(UE_TWO_PI * BobSpeed * Time + Phase)));
}

void ACoinPickup::BeginOverlap(AActor* OverlappedActor, AActor* OtherActor)
{
	// is this the player's pawn?
	APawn* OverlappedPawn = Cast<APawn>(OtherActor);
	if (!OverlappedPawn || !OverlappedPawn->IsPlayerControlled())
	{
		return;
	}

	UE_LOG(LogCoinDemo, Log, TEXT("Coin %s collected at %s by %s at %s"), *GetName(), *GetActorLocation().ToCompactString(), *OverlappedPawn->GetName(), *OverlappedPawn->GetActorLocation().ToCompactString());

	// disable collision so we don't get picked up again
	SetActorEnableCollision(false);

	// tell the game mode to process the pickup
	if (ACoinDemoGameMode* GM = Cast<ACoinDemoGameMode>(GetWorld()->GetAuthGameMode()))
	{
		GM->CoinCollected();
	}

	if (CollectSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, CollectSound, GetActorLocation());
	}

	BP_OnCollected();

	// Tick plays the collect animation and destroys the coin
	CollectedTime = 0.0f;
}
