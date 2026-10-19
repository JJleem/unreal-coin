// Copyright Epic Games, Inc. All Rights Reserved.


#include "CharacterAppearanceComponent.h"
#include "CoinDemo.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "UObject/ConstructorHelpers.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"

UCharacterAppearanceComponent::UCharacterAppearanceComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostUpdateWork;

	static ConstructorHelpers::FClassFinder<AActor> MetaHuman(TEXT("/Game/MetaHumans/NewMetaHumanCharacter/BP_NewMetaHumanCharacter"));
	if (MetaHuman.Succeeded())
	{
		AppearanceClass = MetaHuman.Class;
	}
}

void UCharacterAppearanceComponent::BeginPlay()
{
	Super::BeginPlay();

	ACharacter* Character = Cast<ACharacter>(GetOwner());
	USkeletalMeshComponent* Leader = Character ? Character->GetMesh() : nullptr;
	if (!AppearanceClass || !Leader)
	{
		return;
	}

	FActorSpawnParameters Params;
	Params.Owner = Character;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Appearance = GetWorld()->SpawnActor<AActor>(AppearanceClass, Leader->GetComponentTransform(), Params);
	if (!Appearance)
	{
		return;
	}

	Appearance->SetActorEnableCollision(false);
	Appearance->AttachToComponent(Leader, FAttachmentTransformRules::SnapToTargetNotIncludingScale);

	// the mannequin keeps animating while hidden, and drives every body-skeleton mesh of the appearance
	Leader->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	Leader->SetHiddenInGame(true);

	TArray<USkeletalMeshComponent*> Meshes;
	Appearance->GetComponents(Meshes);

	const USkeleton* BodySkeleton = nullptr;
	for (USkeletalMeshComponent* Mesh : Meshes)
	{
		if (Mesh->GetFName() == TEXT("Body") && Mesh->GetSkeletalMeshAsset())
		{
			BodySkeleton = Mesh->GetSkeletalMeshAsset()->GetSkeleton();
		}
	}

	int32 Followers = 0;
	for (USkeletalMeshComponent* Mesh : Meshes)
	{
		// the face has its own skeleton and animation blueprint that follows the body
		const USkeletalMesh* Asset = Mesh->GetSkeletalMeshAsset();
		if (Asset && Asset->GetSkeleton() == BodySkeleton)
		{
			Mesh->SetAnimInstanceClass(nullptr);
			Mesh->SetLeaderPoseComponent(Leader);
			++Followers;
		}
	}

	UE_LOG(LogCoinDemo, Log, TEXT("Wearing %s: %d meshes follow %s"), *Appearance->GetName(), Followers, *Leader->GetName());
}

void UCharacterAppearanceComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	const ACharacter* Character = Cast<ACharacter>(GetOwner());
	const APlayerController* PC = Character ? Cast<APlayerController>(Character->GetController()) : nullptr;
	if (!Appearance || !PC || !PC->PlayerCameraManager)
	{
		return;
	}

	const float Distance = FVector::Dist(PC->PlayerCameraManager->GetCameraLocation(), Character->GetActorLocation());
	Appearance->SetActorHiddenInGame(Distance < HideWithinCameraDistance);
}

void UCharacterAppearanceComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (Appearance)
	{
		Appearance->Destroy();
		Appearance = nullptr;
	}

	Super::EndPlay(EndPlayReason);
}
