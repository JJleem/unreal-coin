// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TraversalComponent.generated.h"

class ACharacter;
class UAnimMontage;
class UAnimSequence;
class UCharacterMovementComponent;

/** One-shot moves that take over the character for a moment */
UENUM(BlueprintType)
enum class ETraversalAction : uint8
{
	None,
	Slide,
	Roll,
	Mantle
};

/**
 *  Sprint, crouch, slide, roll, ledge climb (mantle) and double jump for a third person character
 *  Animations play on the mesh's DefaultSlot as dynamic montages, so the regular locomotion anim blueprint keeps
 *  working underneath. Roll and climb use the animations' root motion; slide is driven by velocity.
 */
UCLASS(ClassGroup=(CoinDemo), meta=(BlueprintSpawnableComponent))
class UTraversalComponent : public UActorComponent
{
	GENERATED_BODY()

protected:

	/** Sprinting uses the anim blueprint's run, which tops out around this speed without foot sliding */
	UPROPERTY(EditAnywhere, Category="Traversal|Speed", meta = (Units = "cm/s"))
	float SprintSpeed = 750.0f;

	UPROPERTY(EditAnywhere, Category="Traversal|Speed", meta = (Units = "cm/s"))
	float CrouchSpeed = 220.0f;

	/** Speed at the start of a slide */
	UPROPERTY(EditAnywhere, Category="Traversal|Slide", meta = (Units = "cm/s"))
	float SlideSpeed = 1100.0f;

	/** Speed the slide decays to before it ends */
	UPROPERTY(EditAnywhere, Category="Traversal|Slide", meta = (Units = "cm/s"))
	float SlideEndSpeed = 300.0f;

	UPROPERTY(EditAnywhere, Category="Traversal|Slide", meta = (Units = "s"))
	float SlideDuration = 1.0f;

	/** Ground speed needed to start a slide instead of crouching */
	UPROPERTY(EditAnywhere, Category="Traversal|Slide", meta = (Units = "cm/s"))
	float SlideMinSpeed = 600.0f;

	/** Scales the roll animation's root motion (the clip travels about 5.4 m) */
	UPROPERTY(EditAnywhere, Category="Traversal|Roll")
	float RollDistanceScale = 0.6f;

	/** Ledges between these heights above the feet can be climbed */
	UPROPERTY(EditAnywhere, Category="Traversal|Mantle", meta = (Units = "cm"))
	float MantleMinHeight = 50.0f;

	UPROPERTY(EditAnywhere, Category="Traversal|Mantle", meta = (Units = "cm"))
	float MantleMaxHeight = 210.0f;

	/** How far in front of the capsule a wall may be to climb it */
	UPROPERTY(EditAnywhere, Category="Traversal|Mantle", meta = (Units = "cm"))
	float MantleReach = 70.0f;

	UPROPERTY(EditAnywhere, Category="Traversal|Animation")
	TObjectPtr<UAnimSequence> CrouchIdleAnim;

	UPROPERTY(EditAnywhere, Category="Traversal|Animation")
	TObjectPtr<UAnimSequence> CrouchMoveAnim;

	UPROPERTY(EditAnywhere, Category="Traversal|Animation")
	TObjectPtr<UAnimSequence> SlideStartAnim;

	UPROPERTY(EditAnywhere, Category="Traversal|Animation")
	TObjectPtr<UAnimSequence> SlideLoopAnim;

	UPROPERTY(EditAnywhere, Category="Traversal|Animation")
	TObjectPtr<UAnimSequence> SlideExitAnim;

	UPROPERTY(EditAnywhere, Category="Traversal|Animation")
	TObjectPtr<UAnimSequence> RollAnim;

	UPROPERTY(EditAnywhere, Category="Traversal|Animation")
	TObjectPtr<UAnimSequence> ClimbAnim;

	/** Upward distance the climb animation's root motion covers */
	UPROPERTY(EditAnywhere, Category="Traversal|Animation", meta = (Units = "cm"))
	float ClimbAnimHeight = 107.7f;

	/** Current one-shot move */
	ETraversalAction Action = ETraversalAction::None;

	bool bWantsSprint = false;

	/** Looping animation currently on the slot (crouch, sprint, slide) */
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequence> LoopAnim;

	UPROPERTY(Transient)
	TObjectPtr<UAnimMontage> LoopMontage;

	/** Slide state */
	FVector SlideDirection = FVector::ForwardVector;
	float SlideTime = 0.0f;
	float SavedGroundFriction = 0.0f;
	float SavedBrakingDeceleration = 0.0f;

	/** Where a climb should end if its root motion leaves the capsule stuck */
	FVector MantleTarget = FVector::ZeroVector;

	float WalkSpeed = 500.0f;

public:

	/** Constructor */
	UTraversalComponent();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Holds or releases sprint */
	void SetSprinting(bool bSprint);

	/** Crouch toggle; while sprinting fast on the ground it starts a slide instead */
	void CrouchOrSlide();

	/** Rolls forward if on the ground and free */
	bool TryRoll();

	/** Climbs the ledge in front of the character, if there is one. Returns true when a climb started */
	bool TryMantle();

	/** True while a one-shot move owns the character */
	bool IsBusy() const { return Action != ETraversalAction::None; }

	UFUNCTION(BlueprintPure, Category="Traversal")
	ETraversalAction GetAction() const { return Action; }

protected:

	virtual void BeginPlay() override;

	ACharacter* GetCharacter() const;
	UCharacterMovementComponent* GetMovement() const;

	/** Plays a one-shot animation on the slot */
	UAnimMontage* PlayOnce(UAnimSequence* Anim, float PlayRate = 1.0f, float BlendIn = 0.1f, float BlendOut = 0.2f);

	/** Keeps Anim looping on the slot, or clears the loop when Anim is null */
	void SetLoop(UAnimSequence* Anim, float PlayRate);

	void StartSlide();
	void TickSlide(float DeltaTime);
	void EndSlide();

	/** Called when the roll or climb montage ends */
	void OnActionMontageEnded(UAnimMontage* Montage, bool bInterrupted);

	void FinishMantle();
};
