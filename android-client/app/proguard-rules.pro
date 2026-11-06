# ==============================================================================
# AIR BOT: Heavy Obfuscation & Anti-Reverse Engineering Rules (R8 / ProGuard)
# ==============================================================================

# 1. Aggressive Minification & Obfuscation
-repackageclasses 'org.cellsentinel.a'
-allowaccessmodification
-mergeinterfacesaggressively

# 2. Strip Debug Information, File Names, and Line Numbers
-renamesourcefileattribute ''
-keepattributes *Annotation*,Signature
-dontusemixedcaseclassnames

# 3. Strip all Logging statements in production builds
-assumenosideeffects class android.util.Log {
    public static boolean isLoggable(java.lang.String, int);
    public static int v(...);
    public static int d(...);
    public static int i(...);
    public static int w(...);
    public static int e(...);
}

# 4. Obfuscate Native and Internal Telemetry Mechanics
-keepclassmembers class * {
    private *** *(...);
}

# 5. Prevent Decompilers from reconstructing class hierarchies
-flattenpackagehierarchy 'org.cellsentinel.sec'

# Keep essential Android OS entrypoints
-keep class * extends android.app.Activity
-keep class * extends android.app.admin.DeviceAdminReceiver
-keep class * extends android.content.BroadcastReceiver
-keepclassmembers class * extends android.content.BroadcastReceiver {
    public void onReceive(android.content.Context, android.content.Intent);
}
