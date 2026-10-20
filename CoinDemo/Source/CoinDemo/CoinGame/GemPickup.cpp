// Copyright Epic Games, Inc. All Rights Reserved.


#include "GemPickup.h"
#include "HoloStyle.h"
#include "CoinDemo.h"
#include "CoinDemoGameMode.h"
#include "Components/SphereComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

AGemPickup::AGemPickup()
{
	PrimaryActorTick.bCanEverTick = true;

	Sphere = CreateDefaultSubobject<USphereComponent>(TEXT("Collision"));
	RootComponent = Sphere;
	Sphere->SetSphereRadius(70.0f);
	Sphere->SetCollisionObjectType(ECC_WorldDynamic);
	Sphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Sphere->SetCollisionResponseToAllChannels(ECR_Ignore);
	Sphere->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cone(TEXT("/Engine/BasicShapes/Cone.Cone"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hologram(TEXT("/Game/CoinGame/Materials/M_Hologram.M_Hologram"));
	static ConstructorHelpers::FObjectFinder<USoundBase> Chord(TEXT("/Game/Audio/SFX_Gem.SFX_Gem"));
	CollectSound = Chord.Object;

	// the engine cone is 100 cm tall with its pivot in the middle
	auto MakeHalf = [&](const TCHAR* Name, float Pitch, float Z)
	{
		UStaticMeshComponent* Half = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Half->SetupAttachment(RootComponent);
		Half->SetStaticMesh(Cone.Object);
		Half->SetMaterial(0, Hologram.Object);
		Half->SetRelativeLocation(FVector(0.0f, 0.0f, Z));
		Half->SetRelativeRotation(FRotator(Pitch, 0.0f, 0.0f));
		Half->SetRelativeScale3D(FVector(0.5f, 0.5f, 0.45f));
		Half->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Half->SetCastShadow(false);
		return Half;
	};
	Top = MakeHalf(TEXT("Top"), 0.0f, 22.5f);
	Bottom = MakeHalf(TEXT("Bottom"), 180.0f, -22.5f);

	OnActorBeginOverlap.AddDynamic(this, &AGemPickup::BeginOverlap);
}

void AGemPickup::BeginPlay()
{
	Super::BeginPlay();

	// already found in an earlier run: still there, but faded
	const ACoinDemoGameMode* GM = GetWorld()->GetAuthGameMode<ACoinDemoGameMode>();
	const bool bFound = GM && GM->WasGemFoundBefore();
	for (UStaticMeshComponent* Half : { Top, Bottom })
	{
		if (UMaterialInstanceDynamic* Material = Half->CreateDynamicMaterialInstance(0))
		{
			Material->SetVectorParameterValue(TEXT("Color"), Color);
			Material->SetScalarParameterValue(TEXT("Fill"), bFound ? 0.1f : 0.55f);
			Material->SetScalarParameterValue(TEXT("Intensity"), (bFound ? 1.0f : 3.0f) * HoloStyle::GetIntensityScale(GetWorld()));
		}
	}
}

void AGemPickup::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	const float Time = GetWorld()->GetTimeSeconds();
	if (CollectedTime >= 0.0f)
	{
		// spin up, rise and shrink away
		CollectedTime += DeltaTime;
		const float Alpha = FMath::Clamp(CollectedTime / 0.8f, 0.0f, 1.0f);
		AddActorLocalRotation(FRotator(0.0f, 900.0f * DeltaTime, 0.0f));
		AddActorWorldOffset(FVector(0.0f, 0.0f, 150.0f * DeltaTime));
		SetActorScale3D(FVector(FMath::Lerp(1.5f, 0.0f, Alpha * Alpha)));
		if (Alpha >= 1.0f)
		{
			Destroy();
		}
		return;
	}

	AddActorLocalRotation(FRotator(0.0f, 90.0f * DeltaTime, 0.0f));
	Top->SetRelativeLocation(FVector(0.0f, 0.0f, 22.5f + 10.0f * FMath::Sin(Time * 2.0f)));
	Bottom->SetRelativeLocation(FVector(0.0f, 0.0f, -22.5f + 10.0f * FMath::Sin(Time * 2.0f)));
}

void AGemPickup::BeginOverlap(AActor* OverlappedActor, AActor* OtherActor)
{
	const APawn* Pawn = Cast<APawn>(OtherActor);
	if (!Pawn || !Pawn->IsPlayerControlled() || CollectedTime >= 0.0f)
	{
		return;
	}

	SetActorEnableCollision(false);
	CollectedTime = 0.0f;
	if (CollectSound)
	{
		UGameplayStatics::PlaySound2D(this, CollectSound);
	}
	if (ACoinDemoGameMode* GM = GetWorld()->GetAuthGameMode<ACoinDemoGameMode>())
	{
		GM->GemCollected();
	}
	UE_LOG(LogCoinDemo, Log, TEXT("Gem %s collected"), *GetName());
}
