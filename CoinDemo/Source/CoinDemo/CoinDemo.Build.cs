// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class CoinDemo : ModuleRules
{
	public CoinDemo(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			"StateTreeModule",
			"GameplayStateTreeModule",
			"UMG",
			"Slate",
			"SlateCore",
			"NanoGS"
		});

		PrivateDependencyModuleNames.AddRange(new string[] { });

		PublicIncludePaths.AddRange(new string[] {
			"CoinDemo",
			"CoinDemo/CoinGame",
			"CoinDemo/Variant_Platforming",
			"CoinDemo/Variant_Platforming/Animation",
			"CoinDemo/Variant_Combat",
			"CoinDemo/Variant_Combat/AI",
			"CoinDemo/Variant_Combat/Animation",
			"CoinDemo/Variant_Combat/Gameplay",
			"CoinDemo/Variant_Combat/Interfaces",
			"CoinDemo/Variant_Combat/UI",
			"CoinDemo/Variant_SideScrolling",
			"CoinDemo/Variant_SideScrolling/AI",
			"CoinDemo/Variant_SideScrolling/Gameplay",
			"CoinDemo/Variant_SideScrolling/Interfaces",
			"CoinDemo/Variant_SideScrolling/UI"
		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
