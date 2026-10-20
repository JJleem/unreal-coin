// Copyright Epic Games, Inc. All Rights Reserved.


#include "BeforeAfterDemo.h"
#include "CoinDemo.h"
#include "ScanSplatActor.h"
#include "NanoGSGaussianSplatComponent.h"
#include "GaussianSplatAsset.h"
#include "Components/LightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"

ABeforeAfterDemo::ABeforeAfterDemo()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bTickEvenWhenPaused = true;
}

void ABeforeAfterDemo::ApplyCvars(const TArray<FString>& Cvars)
{
	for (const FString& Entry : Cvars)
	{
		FString Name, Value;
		if (!Entry.Split(TEXT("="), &Name, &Value))
		{
			continue;
		}
		if (IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(*Name))
		{
			if (!SavedCvars.Contains(Name))
			{
				SavedCvars.Add(Name, Variable->GetString());
			}
			Variable->Set(*Value, ECVF_SetByConsole);
		}
	}
}

void ABeforeAfterDemo::BeginPlay()
{
	Super::BeginPlay();

	for (TObjectIterator<ULightComponentBase> It; It; ++It)
	{
		if (It->GetWorld() == GetWorld())
		{
			AfterIntensity.Add(*It, It->Intensity);
		}
	}

	for (TObjectIterator<USkyAtmosphereComponent> It; It; ++It)
	{
		if (It->GetWorld() == GetWorld())
		{
			AfterSkyLuminance = It->SkyLuminanceFactor.R;
		}
	}

	// -Before starts in the before state (for screenshots)
	SetAfter(!FParse::Param(FCommandLine::Get(), TEXT("Before")));
}

void ABeforeAfterDemo::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	for (const TPair<FString, FString>& Saved : SavedCvars)
	{
		if (IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(*Saved.Key))
		{
			Variable->Set(*Saved.Value, ECVF_SetByConsole);
		}
	}
	Super::EndPlay(EndPlayReason);
}

void ABeforeAfterDemo::Toggle()
{
	SetAfter(!bAfter);
}

void ABeforeAfterDemo::SetAfter(bool bInAfter)
{
	bAfter = bInAfter;
	ApplyCvars(bAfter ? AfterCvars : BeforeCvars);

	for (TActorIterator<AScanSplatActor> It(GetWorld()); It; ++It)
	{
		if (UGaussianSplatAsset* Asset = bAfter ? AfterScan.Get() : BeforeScan.Get())
		{
			It->GetSplat()->SetSplatAsset(Asset);
		}
	}
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (It->ActorHasTag(MeshTag))
		{
			It->SetActorHiddenInGame(!bAfter);
		}
	}
	for (const TPair<TWeakObjectPtr<ULightComponentBase>, float>& Light : AfterIntensity)
	{
		if (ULightComponent* Component = Cast<ULightComponent>(Light.Key.Get()))
		{
			Component->SetIntensity(Light.Value * (bAfter ? 1.0f : BeforeSunScale));
		}
		else if (USkyLightComponent* Sky = Cast<USkyLightComponent>(Light.Key.Get()))
		{
			Sky->SetIntensity(Light.Value * (bAfter ? 1.0f : BeforeSkyLightScale));
		}
	}
	for (TObjectIterator<USkyAtmosphereComponent> It; It; ++It)
	{
		if (It->GetWorld() == GetWorld())
		{
			const float L = bAfter ? AfterSkyLuminance : BeforeSkyLuminance;
			It->SetSkyLuminanceFactor(FLinearColor(L, L, L));
		}
	}
	UE_LOG(LogCoinDemo, Log, TEXT("Before/after demo: %s"), bAfter ? TEXT("after") : TEXT("before"));
}

void ABeforeAfterDemo::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (PC && PC->WasInputKeyJustPressed(EKeys::B))
	{
		Toggle();
	}
	if (GEngine)
	{
		GEngine->AddOnScreenDebugMessage(9001, 0.0f, bAfter ? FColor(120, 255, 140) : FColor(255, 210, 60),
			bAfter ? TEXT("AFTER  ·  ANNX scan, cleaned + rebuilt ground and buildings + tuned rendering   [B] before")
			       : TEXT("BEFORE  ·  ANNX scan PLY as imported, plugin defaults   [B] after"), true, FVector2D(1.6f, 1.6f));
	}
}
