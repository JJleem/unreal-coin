// Copyright Epic Games, Inc. All Rights Reserved.


#include "GhostRunner.h"
#include "HoloStyle.h"
#include "Animation/AnimInstance.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

AGhostRunner::AGhostRunner(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UGhostMovementComponent>(ACharacter::CharacterMovementComponentName))
{
	PrimaryActorTick.bCanEverTick = true;
	AutoPossessAI = EAutoPossessAI::Disabled;

	GetCapsuleComponent()->InitCapsuleSize(42.0f, 96.0f);
	GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	// the template mannequin with its locomotion anim blueprint
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> Mannequin(TEXT("/Game/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"));
	static ConstructorHelpers::FClassFinder<UAnimInstance> Locomotion(TEXT("/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"));
	USkeletalMeshComponent* Body = GetMesh();
	Body->SetSkeletalMesh(Mannequin.Object);
	Body->SetAnimInstanceClass(Locomotion.Class);
	Body->SetRelativeLocationAndRotation(FVector(0.0f, 0.0f, -96.0f), FRotator(0.0f, -90.0f, 0.0f));
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Body->SetCastShadow(false);

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Hologram(TEXT("/Game/CoinGame/Materials/M_Hologram.M_Hologram"));
	for (int32 i = 0; i < 8; ++i)
	{
		Body->SetMaterial(i, Hologram.Object);
	}

	// the movement component only reports the replayed velocity to the anim blueprint
	GetCharacterMovement()->SetComponentTickEnabled(false);
	GetCharacterMovement()->GravityScale = 0.0f;
}

void AGhostRunner::BeginPlay()
{
	Super::BeginPlay();

	USkeletalMeshComponent* Body = GetMesh();
	for (int32 i = 0; i < Body->GetNumMaterials(); ++i)
	{
		if (UMaterialInstanceDynamic* Material = Body->CreateDynamicMaterialInstance(i))
		{
			Material->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.6f, 0.85f, 1.0f));
			Material->SetScalarParameterValue(TEXT("Fill"), 0.08f);
			Material->SetScalarParameterValue(TEXT("Lines"), 0.0f);
			Material->SetScalarParameterValue(TEXT("Intensity"), 1.2f * HoloStyle::GetIntensityScale(GetWorld()));
		}
	}
	SetActorHiddenInGame(true);
}

void AGhostRunner::Play(const FGhostTrack& InTrack, float InStartTime)
{
	Track = InTrack;
	StartTime = InStartTime;
	SetActorHiddenInGame(Track.Positions.Num() < 2);
}

void AGhostRunner::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	const int32 Count = Track.Positions.Num();
	if (Count < 2)
	{
		return;
	}

	// past the end, the ghost has finished: fade it out of the way
	const float Sample = (GetWorld()->GetTimeSeconds() - StartTime) / Track.Interval;
	if (Sample >= Count - 1)
	{
		SetActorHiddenInGame(true);
		return;
	}

	const int32 Index = FMath::Clamp(FMath::FloorToInt(Sample), 0, Count - 2);
	const float Alpha = Sample - Index;
	const FVector Location = FMath::Lerp(Track.Positions[Index], Track.Positions[Index + 1], Alpha);
	const float Yaw = FMath::Lerp(Track.Yaws[Index], Track.Yaws[Index] + FRotator::NormalizeAxis(Track.Yaws[Index + 1] - Track.Yaws[Index]), Alpha);
	SetActorLocationAndRotation(Location, FRotator(0.0f, Yaw, 0.0f));

	const FVector Velocity = (Track.Positions[Index + 1] - Track.Positions[Index]) / Track.Interval;
	CastChecked<UGhostMovementComponent>(GetCharacterMovement())->SetReplayState(Velocity, Track.Falling[Index] != 0);
}
