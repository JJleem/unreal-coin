// Copyright Epic Games, Inc. All Rights Reserved.

#include "CoinDemoCharacter.h"
#include "Engine/LocalPlayer.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/Controller.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "InputActionValue.h"
#include "CoinDemo.h"
#include "CharacterAppearanceComponent.h"
#include "TraversalComponent.h"
#include "GameFeelComponent.h"
#include "CoinDemoSaveGame.h"
#include "BreakableBarrier.h"
#include "CoinDemoGameMode.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "Engine/LocalPlayer.h"
#include "GameFramework/GameModeBase.h"
#include "Engine/World.h"

ACoinDemoCharacter::ACoinDemoCharacter()
{
	// Set size for collision capsule
	GetCapsuleComponent()->InitCapsuleSize(42.f, 96.0f);
		
	// Don't rotate when the controller rotates. Let that just affect the camera.
	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	// Configure character movement
	GetCharacterMovement()->bOrientRotationToMovement = true;
	GetCharacterMovement()->RotationRate = FRotator(0.0f, 500.0f, 0.0f);

	// Note: For faster iteration times these variables, and many more, can be tweaked in the Character Blueprint
	// instead of recompiling to adjust them
	GetCharacterMovement()->JumpZVelocity = 500.f;
	GetCharacterMovement()->AirControl = 0.35f;
	GetCharacterMovement()->MaxWalkSpeed = 500.f;
	GetCharacterMovement()->MinAnalogWalkSpeed = 20.f;
	GetCharacterMovement()->BrakingDecelerationWalking = 2000.f;
	GetCharacterMovement()->BrakingDecelerationFalling = 1500.0f;

	// Create a camera boom (pulls in towards the player if there is a collision)
	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 400.0f;
	CameraBoom->bUsePawnControlRotation = true;
	CameraBoom->SocketOffset = FVector(0.0f, 0.0f, 40.0f);
	CameraBoom->bEnableCameraLag = true;
	CameraBoom->CameraLagSpeed = 12.0f;

	// Create a follow camera
	FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
	FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	FollowCamera->bUsePawnControlRotation = false;

	Appearance = CreateDefaultSubobject<UCharacterAppearanceComponent>(TEXT("Appearance"));
	Traversal = CreateDefaultSubobject<UTraversalComponent>(TEXT("Traversal"));
	GameFeel = CreateDefaultSubobject<UGameFeelComponent>(TEXT("GameFeel"));

	// Note: The skeletal mesh and anim blueprint references on the Mesh component (inherited from Character) 
	// are set in the derived blueprint asset named ThirdPersonCharacter (to avoid direct content references in C++)
}

void ACoinDemoCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	// Set up action bindings
	if (UEnhancedInputComponent* EnhancedInputComponent = Cast<UEnhancedInputComponent>(PlayerInputComponent)) {
		
		// Jumping (or climbing a ledge in front)
		EnhancedInputComponent->BindAction(JumpAction, ETriggerEvent::Started, this, &ACoinDemoCharacter::DoJumpStart);
		EnhancedInputComponent->BindAction(JumpAction, ETriggerEvent::Completed, this, &ACoinDemoCharacter::DoJumpEnd);

		// Traversal
		CreateTraversalInput();
		EnhancedInputComponent->BindAction(SprintAction, ETriggerEvent::Started, this, &ACoinDemoCharacter::DoSprintStart);
		EnhancedInputComponent->BindAction(SprintAction, ETriggerEvent::Completed, this, &ACoinDemoCharacter::DoSprintEnd);
		EnhancedInputComponent->BindAction(CrouchAction, ETriggerEvent::Started, this, &ACoinDemoCharacter::DoCrouch);
		EnhancedInputComponent->BindAction(RollAction, ETriggerEvent::Started, this, &ACoinDemoCharacter::DoRoll);
		EnhancedInputComponent->BindAction(RestartAction, ETriggerEvent::Started, this, &ACoinDemoCharacter::DoRestart);

		// Moving
		EnhancedInputComponent->BindAction(MoveAction, ETriggerEvent::Triggered, this, &ACoinDemoCharacter::Move);
		EnhancedInputComponent->BindAction(MouseLookAction, ETriggerEvent::Triggered, this, &ACoinDemoCharacter::Look);

		// Looking
		EnhancedInputComponent->BindAction(LookAction, ETriggerEvent::Triggered, this, &ACoinDemoCharacter::Look);
	}
	else
	{
		UE_LOG(LogCoinDemo, Error, TEXT("'%s' Failed to find an Enhanced Input component! This template is built to use the Enhanced Input system. If you intend to use the legacy system, then you will need to update this C++ file."), *GetNameSafe(this));
	}
}

void ACoinDemoCharacter::Move(const FInputActionValue& Value)
{
	// input is a Vector2D
	FVector2D MovementVector = Value.Get<FVector2D>();

	// route the input
	DoMove(MovementVector.X, MovementVector.Y);
}

void ACoinDemoCharacter::Look(const FInputActionValue& Value)
{
	// input is a Vector2D
	FVector2D LookAxisVector = Value.Get<FVector2D>();

	// route the input
	DoLook(LookAxisVector.X, LookAxisVector.Y);
}

void ACoinDemoCharacter::DoMove(float Right, float Forward)
{
	if (GetController() != nullptr && Traversal->GetAction() != ETraversalAction::Mantle)
	{
		// find out which way is forward
		const FRotator Rotation = GetController()->GetControlRotation();
		const FRotator YawRotation(0, Rotation.Yaw, 0);

		// get forward vector
		const FVector ForwardDirection = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X);

		// get right vector 
		const FVector RightDirection = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y);

		// add movement 
		AddMovementInput(ForwardDirection, Forward);
		AddMovementInput(RightDirection, Right);
	}
}

void ACoinDemoCharacter::DoLook(float Yaw, float Pitch)
{
	if (GetController() != nullptr)
	{
		// add yaw and pitch input to controller, scaled by the player's settings
		const UCoinDemoSaveGame* Settings = UCoinDemoSaveGame::LoadOrCreate();
		AddControllerYawInput(Yaw * Settings->MouseSensitivity);
		AddControllerPitchInput(Pitch * Settings->MouseSensitivity * (Settings->bInvertY ? -1.0f : 1.0f));
	}
}

void ACoinDemoCharacter::DoJumpStart()
{
	if (Traversal->IsBusy())
	{
		return;
	}

	// a ledge in front takes priority over jumping
	if (!GetCharacterMovement()->IsFalling() && Traversal->TryMantle())
	{
		return;
	}

	// signal the character to jump
	Jump();
}

void ACoinDemoCharacter::DoJumpEnd()
{
	// signal the character to stop jumping
	StopJumping();
}

void ACoinDemoCharacter::FellOutOfWorld(const UDamageType& DmgType)
{
	// put the player back at the start of the stage
	if (AGameModeBase* GM = GetWorld()->GetAuthGameMode())
	{
		if (AActor* Start = GM->FindPlayerStart(GetController()))
		{
			UE_LOG(LogCoinDemo, Log, TEXT("Fell out of the world at %s, respawning at %s"), *GetActorLocation().ToCompactString(), *Start->GetActorLocation().ToCompactString());
			GetCharacterMovement()->StopMovementImmediately();
			TeleportTo(Start->GetActorLocation(), Start->GetActorRotation());
			return;
		}
	}

	Super::FellOutOfWorld(DmgType);
}

void ACoinDemoCharacter::Landed(const FHitResult& Hit)
{
	// the velocity still holds the fall speed when this is called
	const float ImpactSpeed = -GetCharacterMovement()->Velocity.Z;
	Super::Landed(Hit);
	GameFeel->OnLanded(ImpactSpeed);
}

void ACoinDemoCharacter::MoveBlockedBy(const FHitResult& Impact)
{
	Super::MoveBlockedBy(Impact);

	// running speed, a roll or a slide breaks through barriers; walking into them just stops
	ABreakableBarrier* Barrier = Cast<ABreakableBarrier>(Impact.GetActor());
	const ETraversalAction Action = Traversal->GetAction();
	if (Barrier && (GetVelocity().Size2D() > 600.0f || Action == ETraversalAction::Roll || Action == ETraversalAction::Slide))
	{
		Barrier->Smash(GetActorForwardVector() * 800.0f);
		GameFeel->HitStop();
		GameFeel->AddShake(0.9f);
	}
}

void ACoinDemoCharacter::DoSprintStart()
{
	Traversal->SetSprinting(true);
}

void ACoinDemoCharacter::DoSprintEnd()
{
	Traversal->SetSprinting(false);
}

void ACoinDemoCharacter::DoCrouch()
{
	Traversal->CrouchOrSlide();
}

void ACoinDemoCharacter::DoRoll()
{
	Traversal->TryRoll();
}

void ACoinDemoCharacter::DoRestart()
{
	if (ACoinDemoGameMode* GM = GetWorld()->GetAuthGameMode<ACoinDemoGameMode>())
	{
		GM->RestartStage();
	}
}

void ACoinDemoCharacter::CreateTraversalInput()
{
	if (TraversalMappingContext)
	{
		return;
	}

	auto MakeAction = [this](const TCHAR* Name)
	{
		UInputAction* Action = NewObject<UInputAction>(this, Name);
		Action->ValueType = EInputActionValueType::Boolean;
		return Action;
	};
	SprintAction = MakeAction(TEXT("IA_Sprint"));
	CrouchAction = MakeAction(TEXT("IA_Crouch"));
	RollAction = MakeAction(TEXT("IA_Roll"));
	RestartAction = MakeAction(TEXT("IA_Restart"));

	TraversalMappingContext = NewObject<UInputMappingContext>(this, TEXT("IMC_Traversal"));
	TraversalMappingContext->MapKey(SprintAction, EKeys::LeftShift);
	TraversalMappingContext->MapKey(SprintAction, EKeys::Gamepad_LeftThumbstick);
	TraversalMappingContext->MapKey(CrouchAction, EKeys::C);
	TraversalMappingContext->MapKey(CrouchAction, EKeys::LeftControl);
	TraversalMappingContext->MapKey(CrouchAction, EKeys::Gamepad_FaceButton_Right);
	TraversalMappingContext->MapKey(RollAction, EKeys::Q);
	TraversalMappingContext->MapKey(RollAction, EKeys::Gamepad_FaceButton_Left);
	TraversalMappingContext->MapKey(RestartAction, EKeys::R);
	TraversalMappingContext->MapKey(RestartAction, EKeys::Gamepad_Special_Left);
}

void ACoinDemoCharacter::NotifyControllerChanged()
{
	Super::NotifyControllerChanged();

	CreateTraversalInput();
	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		// scans fall apart when seen from ground level, so keep the camera above the character
		if (PC->PlayerCameraManager)
		{
			PC->PlayerCameraManager->ViewPitchMin = -70.0f;
			PC->PlayerCameraManager->ViewPitchMax = 15.0f;
		}

		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			Subsystem->AddMappingContext(TraversalMappingContext, 1);
		}
	}
}
