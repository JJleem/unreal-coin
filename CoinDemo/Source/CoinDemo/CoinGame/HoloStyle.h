// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "EngineUtils.h"
#include "ScanSplatActor.h"

/**
 *  Shared look of the holographic game layer
 */
namespace HoloStyle
{
	/** Scan stages use a strong fixed exposure (the splats ignore exposure, see build_scan_stages.py), which would
	 *  blow glowing materials out to white, so the hologram brightness is scaled down there */
	inline float GetIntensityScale(const UWorld* World)
	{
		return World && TActorIterator<AScanSplatActor>(const_cast<UWorld*>(World)) ? 0.1f : 1.0f;
	}
}
