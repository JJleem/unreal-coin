// Copyright Epic Games, Inc. All Rights Reserved.


#include "GameFeelComponent.h"
#include "ScanSplatActor.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

UGameFeelComponent::UGameFeelComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostPhysics;

	static ConstructorHelpers::FObjectFinder<USoundBase> Step(TEXT("/Game/Audio/SFX_Step.SFX_Step"));
	static ConstructorHelpers::FObjectFinder<USoundBase> Land(TEXT("/Game/Audio/SFX_Land.SFX_Land"));
	static ConstructorHelpers::FObjectFinder<USoundBase> Whoosh(TEXT("/Game/Audio/SFX_Whoosh.SFX_Whoosh"));
	StepSound = Step.Object;
	LandSound = Land.Object;
	WhooshSound = Whoosh.Object;

	BlobShadow = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BlobShadow"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Plane(TEXT("/Engine/BasicShapes/Plane.Plane"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> ShadowMaterial(TEXT("/Game/CoinGame/Materials/M_BlobShadow.M_BlobShadow"));
	BlobShadow->SetStaticMesh(Plane.Object);
	BlobShadow->SetMaterial(0, ShadowMaterial.Object);
	BlobShadow->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	BlobShadow->SetCastShadow(false);
	BlobShadow->SetUsingAbsoluteLocation(true);
	BlobShadow->SetUsingAbsoluteRotation(true);
	BlobShadow->SetUsingAbsoluteScale(true);
	BlobShadow->SetVisibility(false);
}

ACharacter* UGameFeelComponent::GetCharacter() const
{
	return Cast<ACharacter>(GetOwner());
}

UCameraComponent* UGameFeelComponent::GetCamera() const
{
	return GetOwner() ? GetOwner()->FindComponentByClass<UCameraComponent>() : nullptr;
}

void UGameFeelComponent::BeginPlay()
{
	Super::BeginPlay();

	if (ACharacter* Character = GetCharacter())
	{
		BlobShadow->AttachToComponent(Character->GetRootComponent(), FAttachmentTransformRules::KeepWorldTransform);
	}

	// the template stage has real shadows; the scans can't receive any
	bool bScanStage = false;
	for (TActorIterator<AScanSplatActor> It(GetWorld()); It; ++It)
	{
		bScanStage = true;
		break;
	}
	BlobShadow->SetVisibility(bScanStage);
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (It->ActorHasTag(TEXT("LitGround")))
		{
			const FBox Bounds = It->GetComponentsBoundingBox();
			LitGround.Add(FBox2D(FVector2D(Bounds.Min), FVector2D(Bounds.Max)));
		}
	}
	BlobShadowMaterial = bScanStage ? BlobShadow->CreateDynamicMaterialInstance(0) : nullptr;
}

void UGameFeelComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	// never leave the world in slow motion
	if (HitStopEnd > 0.0)
	{
		UGameplayStatics::SetGlobalTimeDilation(this, 1.0f);
		HitStopEnd = 0.0;
	}
	Super::EndPlay(EndPlayReason);
}

void UGameFeelComponent::AddShake(float Amount)
{
	ShakeAmount = FMath::Clamp(ShakeAmount + Amount, 0.0f, 1.5f);
}

void UGameFeelComponent::HitStop(float RealSeconds)
{
	UGameplayStatics::SetGlobalTimeDilation(this, 0.05f);
	HitStopEnd = FPlatformTime::Seconds() + RealSeconds;
}

void UGameFeelComponent::OnLanded(float ImpactSpeed)
{
	// a normal jump lands at about 500 cm/s, a double jump or a drop much harder
	const float Hardness = FMath::Clamp((ImpactSpeed - 450.0f) / 900.0f, 0.0f, 1.0f);
	if (LandSound && ImpactSpeed > 300.0f)
	{
		UGameplayStatics::PlaySoundAtLocation(this, LandSound, GetOwner()->GetActorLocation(), 0.35f + 0.65f * Hardness, FMath::FRandRange(0.9f, 1.1f));
	}
	AddShake(Hardness * 0.8f);
	StepDistance = 0.0f;
}

void UGameFeelComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	if (HitStopEnd > 0.0 && FPlatformTime::Seconds() >= HitStopEnd)
	{
		UGameplayStatics::SetGlobalTimeDilation(this, 1.0f);
		HitStopEnd = 0.0;
	}

	// time dilation would make the camera effects crawl during a hit stop
	const float RealDelta = FMath::Min(FApp::GetDeltaTime(), 0.1);
	UpdateCamera(RealDelta);
	UpdateFootsteps(DeltaTime);
	UpdateBlobShadow();
}

void UGameFeelComponent::UpdateCamera(float DeltaTime)
{
	ACharacter* Character = GetCharacter();
	UCameraComponent* Camera = GetCamera();
	if (!Character || !Camera)
	{
		return;
	}

	// widen the view with speed, and for the burst of a roll or slide
	const UTraversalComponent* Traversal = Character->FindComponentByClass<UTraversalComponent>();
	const ETraversalAction Action = Traversal ? Traversal->GetAction() : ETraversalAction::None;
	const float Speed = Character->GetVelocity().Size2D();
	float Boost = FMath::Clamp((Speed - 520.0f) / 450.0f, 0.0f, 1.0f);
	if (Action == ETraversalAction::Slide || Action == ETraversalAction::Roll)
	{
		Boost = FMath::Max(Boost, 1.0f);
	}
	Camera->SetFieldOfView(FMath::FInterpTo(Camera->FieldOfView, BaseFOV + SpeedFOV * Boost, DeltaTime, 5.0f));

	// shake: layered sines are smooth enough at this amplitude and need no noise texture
	ShakeTime += DeltaTime;
	ShakeAmount = FMath::FInterpTo(ShakeAmount, 0.0f, DeltaTime, 6.0f);
	const float A = ShakeAmount * ShakeAmount;
	const FRotator Shake(
		A * 2.5f * FMath::Sin(ShakeTime * 53.0f) + A * 1.2f * FMath::Sin(ShakeTime * 31.0f),
		A * 1.5f * FMath::Sin(ShakeTime * 47.0f + 1.3f),
		A * 2.0f * FMath::Sin(ShakeTime * 39.0f + 0.7f));
	Camera->SetRelativeRotation(Shake);
	Camera->SetRelativeLocation(FVector(0.0f, 0.0f, A * -12.0f * FMath::Abs(FMath::Sin(ShakeTime * 25.0f))));

	// whoosh when a roll, slide or climb starts
	if (Action != LastAction && Action != ETraversalAction::None && WhooshSound)
	{
		UGameplayStatics::PlaySoundAtLocation(this, WhooshSound, Character->GetActorLocation(), Action == ETraversalAction::Mantle ? 0.4f : 0.7f, FMath::FRandRange(0.9f, 1.15f));
	}
	LastAction = Action;
}

void UGameFeelComponent::UpdateFootsteps(float DeltaTime)
{
	ACharacter* Character = GetCharacter();
	const UCharacterMovementComponent* Movement = Character ? Character->GetCharacterMovement() : nullptr;
	if (!Movement)
	{
		return;
	}

	const UTraversalComponent* Traversal = Character->FindComponentByClass<UTraversalComponent>();
	if (!Movement->IsMovingOnGround() || (Traversal && Traversal->IsBusy()))
	{
		return;
	}

	const float Speed = Movement->Velocity.Size2D();
	StepDistance += Speed * DeltaTime;
	const float Stride = FMath::GetMappedRangeValueClamped(FVector2D(300.0f, 750.0f), FVector2D(WalkStride, SprintStride), Speed);
	if (StepDistance >= Stride && StepSound)
	{
		StepDistance = 0.0f;
		const float Volume = (Character->bIsCrouched ? 0.12f : 0.25f) + 0.2f * FMath::Clamp(Speed / 750.0f, 0.0f, 1.0f);
		const FVector Feet = Character->GetActorLocation() - FVector(0.0f, 0.0f, Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
		UGameplayStatics::PlaySoundAtLocation(this, StepSound, Feet, Volume, FMath::FRandRange(0.8f, 1.2f));
	}
}

void UGameFeelComponent::UpdateBlobShadow()
{
	ACharacter* Character = GetCharacter();
	if (!Character || !BlobShadow->IsVisible())
	{
		return;
	}

	// find the floor below, ignoring the character itself
	const FVector Start = Character->GetActorLocation();
	for (const FBox2D& Area : LitGround)
	{
		if (Area.IsInside(FVector2D(Start)))
		{
			BlobShadowMaterial->SetScalarParameterValue(TEXT("Strength"), 0.0f);
			return;
		}
	}
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(BlobShadow), false, Character);
	if (!GetWorld()->LineTraceSingleByChannel(Hit, Start, Start - FVector(0.0f, 0.0f, 2000.0f), ECC_Visibility, Params))
	{
		BlobShadowMaterial->SetScalarParameterValue(TEXT("Strength"), 0.0f);
		return;
	}

	// the shadow shrinks and fades as the character rises above it
	const float Height = Hit.Distance - Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	const float Fade = FMath::Clamp(1.0f - Height / 700.0f, 0.0f, 1.0f);
	BlobShadow->SetWorldLocationAndRotation(Hit.ImpactPoint + Hit.ImpactNormal * 3.0f, FRotationMatrix::MakeFromZ(Hit.ImpactNormal).Rotator());
	BlobShadow->SetWorldScale3D(FVector(FMath::Lerp(0.7f, 1.4f, Fade)));
	BlobShadowMaterial->SetScalarParameterValue(TEXT("Strength"), 0.85f * Fade);
}
