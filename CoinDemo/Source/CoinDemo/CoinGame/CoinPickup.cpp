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

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> ShapeMaterial(TEXT("/Game/CoinGame/Materials/M_Coin.M_Coin"));
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

	// close enough: fly into the player, speeding up so it can't be outrun
	const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
	if (Player && (MagnetSpeed > 0.0f || FVector::DistSquared(Player->GetActorLocation(), GetActorLocation()) < FMath::Square(MagnetRadius)))
	{
		MagnetSpeed = FMath::Max(MagnetSpeed, 400.0f) + 3000.0f * DeltaTime;
		const FVector Target = Player->GetActorLocation() + FVector(0.0f, 0.0f, 20.0f);
		SetActorLocation(FMath::VInterpConstantTo(GetActorLocation(), Target, DeltaTime, MagnetSpeed));
		Mesh->SetRelativeLocation(FMath::VInterpTo(Mesh->GetRelativeLocation(), FVector::ZeroVector, DeltaTime, 10.0f));
		return;
	}

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

	// the chime climbs with the combo
	if (CollectSound)
	{
		const ACoinDemoGameMode* GM = GetWorld()->GetAuthGameMode<ACoinDemoGameMode>();
		const int32 Combo = GM ? GM->GetCombo() : 1;
		UGameplayStatics::PlaySoundAtLocation(this, CollectSound, GetActorLocation(), 1.0f, FMath::Min(1.0f + 0.08f * (Combo - 1), 1.8f));
	}

	BP_OnCollected();

	// Tick plays the collect animation and destroys the coin
	CollectedTime = 0.0f;
}
