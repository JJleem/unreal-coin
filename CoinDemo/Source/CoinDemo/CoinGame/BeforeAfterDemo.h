// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BeforeAfterDemo.generated.h"

class UGaussianSplatAsset;

/**
 *  Shows a scan stage "before" (the ANNX PLY as imported, plugin default rendering) and "after" (cleaned scan, the
 *  rebuilt ground and buildings, tone corrected splats, TSR) and switches between them with B, for demos.
 *  Also applies the after state's render settings when play starts, and restores them when the level ends.
 */
UCLASS()
class ABeforeAfterDemo : public AActor
{
	GENERATED_BODY()

protected:

	/** Scan shown in the before state, normally the raw ANNX PLY import */
	UPROPERTY(EditAnywhere, Category="Demo")
	TObjectPtr<UGaussianSplatAsset> BeforeScan;

	/** Scan shown in the after state, normally the cleaned and trimmed one the level was built with */
	UPROPERTY(EditAnywhere, Category="Demo")
	TObjectPtr<UGaussianSplatAsset> AfterScan;

	/** Actors with this tag are the rebuilt meshes: hidden in the before state */
	UPROPERTY(EditAnywhere, Category="Demo")
	FName MeshTag = TEXT("LitGround");

	/** Console variables of each state, "name=value" */
	UPROPERTY(EditAnywhere, Category="Demo")
	TArray<FString> BeforeCvars = { TEXT("r.AntiAliasingMethod=1"), TEXT("gs.ToneCorrection=0") };

	UPROPERTY(EditAnywhere, Category="Demo")
	TArray<FString> AfterCvars = { TEXT("r.AntiAliasingMethod=4"), TEXT("gs.ToneCorrection=1") };

	/** The after lighting is tuned for the meshes; the before state goes back to the stage's: sun and sky light
	 *  intensities multiplied by these, and the sky atmosphere's luminance factor set to BeforeSkyLuminance */
	UPROPERTY(EditAnywhere, Category="Demo")
	float BeforeSunScale = 1.0f;

	UPROPERTY(EditAnywhere, Category="Demo")
	float BeforeSkyLightScale = 1.0f;

	UPROPERTY(EditAnywhere, Category="Demo")
	float BeforeSkyLuminance = 1.0f;

	float AfterSkyLuminance = 1.0f;

	bool bAfter = true;

	/** Values the console variables had before play, restored at the end */
	TMap<FString, FString> SavedCvars;

	/** After state light intensities, by component */
	TMap<TWeakObjectPtr<class ULightComponentBase>, float> AfterIntensity;

public:

	ABeforeAfterDemo();

	/** Switches between before and after */
	UFUNCTION(BlueprintCallable, Category="Demo")
	void Toggle();

	/** Sets the state */
	UFUNCTION(BlueprintCallable, Category="Demo")
	void SetAfter(bool bInAfter);

	bool IsAfter() const { return bAfter; }

protected:

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	void ApplyCvars(const TArray<FString>& Cvars);
};
