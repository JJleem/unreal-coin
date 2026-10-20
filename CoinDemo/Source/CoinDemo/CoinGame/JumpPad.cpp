// Copyright Epic Games, Inc. All Rights Reserved.


#include "JumpPad.h"
#include "HoloStyle.h"
#include "CoinDemo.h"
#include "GameFeelComponent.h"
#include "TraversalComponent.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

AJumpPad::AJumpPad()
{
	PrimaryActorTick.bCanEverTick = true;

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	RootComponent = Trigger;
	Trigger->SetBoxExtent(FVector(90.0f, 90.0f, 40.0f));
	Trigger->SetCollisionProfileName(TEXT("OverlapAllDynamic"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hologram(TEXT("/Game/CoinGame/Materials/M_Hologram.M_Hologram"));
	static ConstructorHelpers::FObjectFinder<USoundBase> Launch(TEXT("/Game/Audio/SFX_Launch.SFX_Launch"));
	LaunchSound = Launch.Object;

	// a flat disc on the ground, the trigger's bottom at the pivot
	Pad = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pad"));
	Pad->SetupAttachment(RootComponent);
	Pad->SetStaticMesh(Cylinder.Object);
	Pad->SetMaterial(0, Hologram.Object);
	Pad->SetRelativeLocation(FVector(0.0f, 0.0f, -35.0f));
	Pad->SetRelativeScale3D(FVector(1.8f, 1.8f, 0.1f));
	Pad->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Pad->SetCastShadow(false);

	// and a faint column of light above it
	Beam = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Beam"));
	Beam->SetupAttachment(RootComponent);
	Beam->SetStaticMesh(Cylinder.Object);
	Beam->SetMaterial(0, Hologram.Object);
	Beam->SetRelativeLocation(FVector(0.0f, 0.0f, 360.0f));
	Beam->SetRelativeScale3D(FVector(1.2f, 1.2f, 8.0f));
	Beam->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Beam->SetCastShadow(false);

	OnActorBeginOverlap.AddDynamic(this, &AJumpPad::BeginOverlap);
}

void AJumpPad::BeginPlay()
{
	Super::BeginPlay();

	IntensityScale = HoloStyle::GetIntensityScale(GetWorld());
	PadMaterial = Pad->CreateDynamicMaterialInstance(0);
	PadMaterial->SetVectorParameterValue(TEXT("Color"), Color);
	if (UMaterialInstanceDynamic* BeamMaterial = Beam->CreateDynamicMaterialInstance(0))
	{
		BeamMaterial->SetVectorParameterValue(TEXT("Color"), Color);
		BeamMaterial->SetScalarParameterValue(TEXT("Fill"), 0.03f);
		BeamMaterial->SetScalarParameterValue(TEXT("Lines"), 0.0f);
		BeamMaterial->SetScalarParameterValue(TEXT("Intensity"), 1.0f * IntensityScale);
	}
}

void AJumpPad::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	// breathe gently, flash on launch
	const float Since = GetWorld()->GetTimeSeconds() - LastLaunchTime;
	const float Flash = FMath::Clamp(1.0f - Since / 0.4f, 0.0f, 1.0f);
	const float Breath = 0.5f + 0.5f * FMath::Sin(GetWorld()->GetTimeSeconds() * 3.0f);
	PadMaterial->SetScalarParameterValue(TEXT("Fill"), 0.25f + 0.2f * Breath + 0.55f * Flash);
	PadMaterial->SetScalarParameterValue(TEXT("Intensity"), (2.0f + 4.0f * Flash) * IntensityScale);
}

void AJumpPad::BeginOverlap(AActor* OverlappedActor, AActor* OtherActor)
{
	ACharacter* Character = Cast<ACharacter>(OtherActor);
	if (!Character || !Character->IsPlayerControlled())
	{
		return;
	}

	// a ballistic arc that peaks ArcHeight above the higher end and comes down on the target
	const UCharacterMovementComponent* Movement = Character->GetCharacterMovement();
	const float Gravity = FMath::Max(-Movement->GetGravityZ(), 1.0f);
	const FVector Start = Character->GetActorLocation();
	const FVector Goal = Target + FVector(0.0f, 0.0f, Character->GetSimpleCollisionHalfHeight());
	const float Apex = FMath::Max(Start.Z, Goal.Z) + ArcHeight;
	const float Up = FMath::Sqrt(2.0f * Gravity * (Apex - Start.Z));
	const float Time = Up / Gravity + FMath::Sqrt(2.0f * (Apex - Goal.Z) / Gravity);
	const FVector Horizontal = (Goal - Start) * FVector(1.0f, 1.0f, 0.0f) / Time;
	Character->LaunchCharacter(Horizontal + FVector(0.0f, 0.0f, Up), true, true);
	if (UTraversalComponent* Traversal = Character->FindComponentByClass<UTraversalComponent>())
	{
		Traversal->OnLaunched();
	}

	LastLaunchTime = GetWorld()->GetTimeSeconds();
	if (LaunchSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, LaunchSound, GetActorLocation());
	}
	if (UGameFeelComponent* Feel = Character->FindComponentByClass<UGameFeelComponent>())
	{
		Feel->AddShake(0.5f);
	}
	UE_LOG(LogCoinDemo, Log, TEXT("Jump pad %s launched %s towards %s"), *GetName(), *Character->GetName(), *Target.ToCompactString());
}
