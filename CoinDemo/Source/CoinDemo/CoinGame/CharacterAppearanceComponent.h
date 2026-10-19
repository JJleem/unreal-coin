// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CharacterAppearanceComponent.generated.h"

/**
 *  Dresses a character in another actor's look, typically an assembled MetaHuman blueprint
 *  The owner's own mesh keeps running the animation blueprint but is hidden; the appearance actor is attached to it
 *  and its body meshes follow that pose, so every animation made for the mannequin plays on the MetaHuman as well
 */
UCLASS(ClassGroup=(CoinDemo), meta=(BlueprintSpawnableComponent))
class UCharacterAppearanceComponent : public UActorComponent
{
	GENERATED_BODY()

protected:

	/** Actor to wear, e.g. an assembled MetaHuman blueprint. Leave empty to keep the mannequin */
	UPROPERTY(EditAnywhere, Category="Appearance")
	TSubclassOf<AActor> AppearanceClass;

	/** The spawned appearance actor */
	UPROPERTY(Transient)
	TObjectPtr<AActor> Appearance;

public:

	/** Constructor */
	UCharacterAppearanceComponent();

	/** Returns the spawned appearance actor, if any */
	AActor* GetAppearance() const { return Appearance; }

protected:

	/** Spawns the appearance and hooks it to the owner's mesh */
	virtual void BeginPlay() override;

	/** Destroys the appearance with its owner */
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
};
