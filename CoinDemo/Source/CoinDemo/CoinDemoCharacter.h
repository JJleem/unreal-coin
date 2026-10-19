// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Logging/LogMacros.h"
#include "CoinDemoCharacter.generated.h"

class USpringArmComponent;
class UCharacterAppearanceComponent;
class UTraversalComponent;
class UInputMappingContext;
class UCameraComponent;
class UInputAction;
struct FInputActionValue;

DECLARE_LOG_CATEGORY_EXTERN(LogTemplateCharacter, Log, All);

/**
 *  A simple player-controllable third person character
 *  Implements a controllable orbiting camera
 */
UCLASS(abstract)
class ACoinDemoCharacter : public ACharacter
{
	GENERATED_BODY()

	/** Camera boom positioning the camera behind the character */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	USpringArmComponent* CameraBoom;

	/** Wears the MetaHuman look on top of the animated mannequin */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UCharacterAppearanceComponent* Appearance;

	/** Sprint, crouch, slide, roll, ledge climb and double jump */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UTraversalComponent* Traversal;

	/** Follow camera */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Components", meta = (AllowPrivateAccess = "true"))
	UCameraComponent* FollowCamera;
	
protected:

	/** Jump Input Action */
	UPROPERTY(EditAnywhere, Category="Input")
	UInputAction* JumpAction;

	/** Move Input Action */
	UPROPERTY(EditAnywhere, Category="Input")
	UInputAction* MoveAction;

	/** Look Input Action */
	UPROPERTY(EditAnywhere, Category="Input")
	UInputAction* LookAction;

	/** Mouse Look Input Action */
	UPROPERTY(EditAnywhere, Category="Input")
	UInputAction* MouseLookAction;

	/** Traversal input, created at runtime so the controls live in code: Shift sprint, C crouch/slide, Q roll */
	UPROPERTY(Transient)
	TObjectPtr<UInputAction> SprintAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> CrouchAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> RollAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> RestartAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> TraversalMappingContext;

public:

	/** Constructor */
	ACoinDemoCharacter();	

protected:

	/** Initialize input action bindings */
	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

	/** Smashes breakable barriers the character runs, rolls or slides into */
	virtual void MoveBlockedBy(const FHitResult& Impact) override;

	/** Adds the traversal key mappings for the local player */
	virtual void NotifyControllerChanged() override;

	/** Creates the runtime traversal input actions and their key mappings */
	void CreateTraversalInput();

	/** Respawns at the player start instead of being destroyed when falling below the stage's Kill Z */
	virtual void FellOutOfWorld(const class UDamageType& DmgType) override;

protected:

	/** Called for movement input */
	void Move(const FInputActionValue& Value);

	/** Called for looking input */
	void Look(const FInputActionValue& Value);

public:

	/** Handles move inputs from either controls or UI interfaces */
	UFUNCTION(BlueprintCallable, Category="Input")
	virtual void DoMove(float Right, float Forward);

	/** Handles look inputs from either controls or UI interfaces */
	UFUNCTION(BlueprintCallable, Category="Input")
	virtual void DoLook(float Yaw, float Pitch);

	/** Handles jump pressed inputs from either controls or UI interfaces */
	UFUNCTION(BlueprintCallable, Category="Input")
	virtual void DoJumpStart();

	/** Handles jump pressed inputs from either controls or UI interfaces */
	UFUNCTION(BlueprintCallable, Category="Input")
	virtual void DoJumpEnd();

	/** Starts sprinting */
	UFUNCTION(BlueprintCallable, Category="Input")
	void DoSprintStart();

	/** Stops sprinting */
	UFUNCTION(BlueprintCallable, Category="Input")
	void DoSprintEnd();

	/** Toggles crouch, or slides when sprinting */
	UFUNCTION(BlueprintCallable, Category="Input")
	void DoCrouch();

	/** Rolls forward */
	UFUNCTION(BlueprintCallable, Category="Input")
	void DoRoll();

	/** Restarts the current stage */
	UFUNCTION(BlueprintCallable, Category="Input")
	void DoRestart();

public:

	/** Returns CameraBoom subobject **/
	FORCEINLINE class USpringArmComponent* GetCameraBoom() const { return CameraBoom; }

	/** Returns FollowCamera subobject **/
	FORCEINLINE class UCameraComponent* GetFollowCamera() const { return FollowCamera; }
};

