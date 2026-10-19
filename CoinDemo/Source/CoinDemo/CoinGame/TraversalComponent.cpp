// Copyright Epic Games, Inc. All Rights Reserved.


#include "TraversalComponent.h"
#include "CoinDemo.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace TraversalAnims
{
	const FName Slot(TEXT("DefaultSlot"));

	UAnimSequence* Find(const TCHAR* Name)
	{
		ConstructorHelpers::FObjectFinder<UAnimSequence> Anim(*FString::Printf(TEXT("/Game/Quaternius/Mannequin/%s"), Name));
		return Anim.Object;
	}
}

UTraversalComponent::UTraversalComponent()
{
	PrimaryComponentTick.bCanEverTick = true;

	// Quaternius Universal Animation Library, retargeted by Scripts/import_animations.py
	CrouchIdleAnim = TraversalAnims::Find(TEXT("UAL1_StandardRig_Crouch_Idle_Loop"));
	CrouchMoveAnim = TraversalAnims::Find(TEXT("UAL1_StandardRig_Crouch_Fwd_Loop"));
	SprintAnim = TraversalAnims::Find(TEXT("UAL1_StandardRig_Sprint_Loop"));
	SlideStartAnim = TraversalAnims::Find(TEXT("UAL2_StandardSlide_Start"));
	SlideLoopAnim = TraversalAnims::Find(TEXT("UAL2_StandardSlide_Loop"));
	SlideExitAnim = TraversalAnims::Find(TEXT("UAL2_StandardSlide_Exit"));
	RollAnim = TraversalAnims::Find(TEXT("UAL1_StandardRig_Roll_RM"));
	ClimbAnim = TraversalAnims::Find(TEXT("UAL2_StandardClimbUp_1m_RM"));
}

ACharacter* UTraversalComponent::GetCharacter() const
{
	return Cast<ACharacter>(GetOwner());
}

UCharacterMovementComponent* UTraversalComponent::GetMovement() const
{
	ACharacter* Character = GetCharacter();
	return Character ? Character->GetCharacterMovement() : nullptr;
}

void UTraversalComponent::BeginPlay()
{
	Super::BeginPlay();

	ACharacter* Character = GetCharacter();
	UCharacterMovementComponent* Movement = GetMovement();
	if (!Character || !Movement)
	{
		return;
	}

	WalkSpeed = Movement->MaxWalkSpeed;
	Movement->GetNavAgentPropertiesRef().bCanCrouch = true;
	Movement->SetCrouchedHalfHeight(60.0f);
	Movement->MaxWalkSpeedCrouched = CrouchSpeed;
	Character->JumpMaxCount = 2;
}

UAnimMontage* UTraversalComponent::PlayOnce(UAnimSequence* Anim, float PlayRate, float BlendIn, float BlendOut)
{
	ACharacter* Character = GetCharacter();
	UAnimInstance* AnimInstance = Character ? Character->GetMesh()->GetAnimInstance() : nullptr;
	if (!Anim || !AnimInstance)
	{
		return nullptr;
	}
	return AnimInstance->PlaySlotAnimationAsDynamicMontage(Anim, TraversalAnims::Slot, BlendIn, BlendOut, PlayRate, 1);
}

void UTraversalComponent::SetLoop(UAnimSequence* Anim, float PlayRate)
{
	ACharacter* Character = GetCharacter();
	UAnimInstance* AnimInstance = Character ? Character->GetMesh()->GetAnimInstance() : nullptr;
	if (!AnimInstance)
	{
		return;
	}

	if (Anim == LoopAnim && LoopMontage && AnimInstance->Montage_IsPlaying(LoopMontage))
	{
		AnimInstance->Montage_SetPlayRate(LoopMontage, PlayRate);
		return;
	}

	if (LoopMontage && AnimInstance->Montage_IsPlaying(LoopMontage))
	{
		AnimInstance->Montage_Stop(0.2f, LoopMontage);
	}

	LoopAnim = Anim;
	LoopMontage = Anim ? AnimInstance->PlaySlotAnimationAsDynamicMontage(Anim, TraversalAnims::Slot, 0.2f, 0.2f, PlayRate, 1000) : nullptr;
}

void UTraversalComponent::SetSprinting(bool bSprint)
{
	bWantsSprint = bSprint;
}

void UTraversalComponent::CrouchOrSlide()
{
	ACharacter* Character = GetCharacter();
	UCharacterMovementComponent* Movement = GetMovement();
	if (!Character || !Movement || IsBusy())
	{
		return;
	}

	if (Movement->IsMovingOnGround() && bWantsSprint && Movement->Velocity.Size2D() >= SlideMinSpeed)
	{
		StartSlide();
	}
	else if (Character->bIsCrouched)
	{
		Character->UnCrouch();
	}
	else
	{
		Character->Crouch();
	}
}

void UTraversalComponent::StartSlide()
{
	ACharacter* Character = GetCharacter();
	UCharacterMovementComponent* Movement = GetMovement();

	Action = ETraversalAction::Slide;
	SlideTime = 0.0f;
	SlideDirection = Movement->Velocity.GetSafeNormal2D();

	// no friction: the slide speed is set directly every frame
	SavedGroundFriction = Movement->GroundFriction;
	SavedBrakingDeceleration = Movement->BrakingDecelerationWalking;
	Movement->GroundFriction = 0.0f;
	Movement->BrakingDecelerationWalking = 0.0f;
	Movement->MaxWalkSpeedCrouched = SlideSpeed;
	Character->Crouch();

	SetLoop(nullptr, 1.0f);
	PlayOnce(SlideStartAnim, 1.2f, 0.1f, 0.1f);
}

void UTraversalComponent::TickSlide(float DeltaTime)
{
	UCharacterMovementComponent* Movement = GetMovement();
	SlideTime += DeltaTime;

	// ease out from the slide speed to the end speed
	const float Alpha = FMath::Clamp(SlideTime / SlideDuration, 0.0f, 1.0f);
	const float Speed = FMath::Lerp(SlideSpeed, SlideEndSpeed, 1.0f - FMath::Square(1.0f - Alpha));
	Movement->Velocity = SlideDirection * Speed + FVector(0.0f, 0.0f, Movement->Velocity.Z);

	// drop from the start pose into the sliding loop
	if (SlideStartAnim && LoopAnim != SlideLoopAnim && SlideTime > SlideStartAnim->GetPlayLength() / 1.2f * 0.8f)
	{
		SetLoop(SlideLoopAnim, 1.0f);
	}

	// stop at the end, against a wall or off a ledge
	if (Alpha >= 1.0f || !Movement->IsMovingOnGround() || Movement->Velocity.Size2D() < SlideEndSpeed * 0.5f)
	{
		EndSlide();
	}
}

void UTraversalComponent::EndSlide()
{
	ACharacter* Character = GetCharacter();
	UCharacterMovementComponent* Movement = GetMovement();

	Action = ETraversalAction::None;
	Movement->GroundFriction = SavedGroundFriction;
	Movement->BrakingDecelerationWalking = SavedBrakingDeceleration;
	Movement->MaxWalkSpeedCrouched = CrouchSpeed;

	SetLoop(nullptr, 1.0f);
	PlayOnce(SlideExitAnim, 1.0f, 0.1f, 0.25f);
	Character->UnCrouch();
}

bool UTraversalComponent::TryRoll()
{
	ACharacter* Character = GetCharacter();
	UCharacterMovementComponent* Movement = GetMovement();
	if (!Character || !Movement || IsBusy() || !Movement->IsMovingOnGround())
	{
		return false;
	}

	SetLoop(nullptr, 1.0f);
	UAnimMontage* Montage = PlayOnce(RollAnim, 1.1f, 0.05f, 0.2f);
	if (!Montage)
	{
		return false;
	}

	// roll in the input direction, low enough to pass under obstacles
	const FVector Input = Movement->GetLastInputVector().GetSafeNormal2D();
	if (!Input.IsNearlyZero())
	{
		Character->SetActorRotation(Input.Rotation());
	}
	Character->Crouch();
	Character->SetAnimRootMotionTranslationScale(RollDistanceScale);
	Action = ETraversalAction::Roll;

	FOnMontageEnded Ended;
	Ended.BindUObject(this, &UTraversalComponent::OnActionMontageEnded);
	Character->GetMesh()->GetAnimInstance()->Montage_SetEndDelegate(Ended, Montage);
	return true;
}

bool UTraversalComponent::TryMantle()
{
	ACharacter* Character = GetCharacter();
	UCharacterMovementComponent* Movement = GetMovement();
	if (!Character || !Movement || IsBusy() || !ClimbAnim)
	{
		return false;
	}

	UWorld* World = GetWorld();
	const UCapsuleComponent* Capsule = Character->GetCapsuleComponent();
	const float HalfHeight = Capsule->GetScaledCapsuleHalfHeight();
	const float Radius = Capsule->GetScaledCapsuleRadius();
	const FVector Location = Character->GetActorLocation();
	const FVector Feet = Location - FVector(0.0f, 0.0f, HalfHeight);
	const FVector Forward = Character->GetActorForwardVector().GetSafeNormal2D();

	FCollisionQueryParams Params(SCENE_QUERY_STAT(Mantle), false, Character);

	// a wall in front, at knee or chest height
	FHitResult Wall;
	bool bWall = false;
	for (const float Height : { MantleMinHeight + 10.0f, 100.0f, 150.0f })
	{
		const FVector Start = Feet + FVector(0.0f, 0.0f, Height);
		if (World->LineTraceSingleByChannel(Wall, Start, Start + Forward * (Radius + MantleReach), ECC_Visibility, Params)
			&& FVector::DotProduct(Wall.ImpactNormal.GetSafeNormal2D(), -Forward) > 0.5f)
		{
			bWall = true;
			break;
		}
	}
	if (!bWall)
	{
		return false;
	}

	// the top of that wall, a little past its face
	const FVector WallInward = -Wall.ImpactNormal.GetSafeNormal2D();
	const FVector Probe = Wall.ImpactPoint + WallInward * 30.0f;
	FHitResult Ledge;
	if (!World->LineTraceSingleByChannel(Ledge, FVector(Probe.X, Probe.Y, Feet.Z + MantleMaxHeight + 30.0f), FVector(Probe.X, Probe.Y, Feet.Z + MantleMinHeight - 5.0f), ECC_Visibility, Params)
		|| Ledge.bStartPenetrating || Ledge.ImpactNormal.Z < 0.7f)
	{
		return false;
	}

	const float LedgeHeight = Ledge.ImpactPoint.Z - Feet.Z;
	if (LedgeHeight < MantleMinHeight || LedgeHeight > MantleMaxHeight)
	{
		return false;
	}

	// there has to be room to stand on top
	MantleTarget = Ledge.ImpactPoint + WallInward * (Radius + 10.0f) + FVector(0.0f, 0.0f, HalfHeight + 2.0f);
	if (World->OverlapBlockingTestByChannel(MantleTarget, FQuat::Identity, ECC_Pawn, FCollisionShape::MakeCapsule(Radius, HalfHeight), Params))
	{
		return false;
	}

	// face the wall and let the climb animation carry the capsule, scaled to the ledge height
	Character->SetActorRotation(WallInward.Rotation());
	SetLoop(nullptr, 1.0f);
	UAnimMontage* Montage = PlayOnce(ClimbAnim, 1.0f, 0.05f, 0.15f);
	if (!Montage)
	{
		return false;
	}

	Action = ETraversalAction::Mantle;
	Character->SetAnimRootMotionTranslationScale(LedgeHeight / ClimbAnimHeight);
	Character->SetActorEnableCollision(false);
	Movement->StopMovementImmediately();
	Movement->SetMovementMode(MOVE_Flying);

	FOnMontageEnded Ended;
	Ended.BindUObject(this, &UTraversalComponent::OnActionMontageEnded);
	Character->GetMesh()->GetAnimInstance()->Montage_SetEndDelegate(Ended, Montage);

	UE_LOG(LogCoinDemo, Log, TEXT("Mantle: ledge %.0f cm high"), LedgeHeight);
	return true;
}

void UTraversalComponent::FinishMantle()
{
	ACharacter* Character = GetCharacter();
	UCharacterMovementComponent* Movement = GetMovement();
	const UCapsuleComponent* Capsule = Character->GetCapsuleComponent();

	// root motion runs without collision; if it ended inside something, put the capsule on the ledge
	FCollisionQueryParams Params(SCENE_QUERY_STAT(Mantle), false, Character);
	if (GetWorld()->OverlapBlockingTestByChannel(Character->GetActorLocation(), FQuat::Identity, ECC_Pawn,
		FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight()), Params))
	{
		Character->SetActorLocation(MantleTarget);
	}

	Character->SetActorEnableCollision(true);
	Movement->SetMovementMode(MOVE_Walking);
}

void UTraversalComponent::OnActionMontageEnded(UAnimMontage* Montage, bool bInterrupted)
{
	ACharacter* Character = GetCharacter();
	if (!Character)
	{
		return;
	}

	if (Action == ETraversalAction::Mantle)
	{
		FinishMantle();
	}
	else if (Action == ETraversalAction::Roll)
	{
		Character->UnCrouch();
	}

	Character->SetAnimRootMotionTranslationScale(1.0f);
	Action = ETraversalAction::None;
}

void UTraversalComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	ACharacter* Character = GetCharacter();
	UCharacterMovementComponent* Movement = GetMovement();
	if (!Character || !Movement)
	{
		return;
	}

	if (Action == ETraversalAction::Slide)
	{
		TickSlide(DeltaTime);
		return;
	}
	if (Action != ETraversalAction::None)
	{
		return;
	}

	const bool bSprinting = bWantsSprint && !Character->bIsCrouched;
	Movement->MaxWalkSpeed = bSprinting ? SprintSpeed : WalkSpeed;

	// locomotion the anim blueprint doesn't cover: crouching and sprinting
	const float Speed = Movement->Velocity.Size2D();
	if (!Movement->IsMovingOnGround())
	{
		SetLoop(nullptr, 1.0f);
	}
	else if (Character->bIsCrouched)
	{
		if (Speed > 20.0f)
		{
			SetLoop(CrouchMoveAnim, FMath::Clamp(Speed / CrouchSpeed, 0.5f, 1.5f));
		}
		else
		{
			SetLoop(CrouchIdleAnim, 1.0f);
		}
	}
	else if (bSprinting && Speed > WalkSpeed + 50.0f)
	{
		SetLoop(SprintAnim, FMath::Clamp(Speed / SprintSpeed, 0.6f, 1.3f));
	}
	else
	{
		SetLoop(nullptr, 1.0f);
	}
}
