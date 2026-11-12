#!/bin/sh
set -eu

: "${ANDROID_JAR:?Set ANDROID_JAR to the Android SDK platform android.jar}"
: "${ANDROID_BUILD_TOOLS:?Set ANDROID_BUILD_TOOLS to an SDK build-tools directory}"
: "${JAVA_HOME:?Set JAVA_HOME to the JDK directory}"
: "${KEYSTORE:?Set KEYSTORE to your Android signing keystore}"

source_dir=$(CDPATH='' cd "$(dirname "$0")" && pwd)
output=${1:-NetHunter-Launcher.apk}
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
mkdir "$temporary/classes" "$temporary/dex"

"$JAVA_HOME/bin/javac" --release 8 -classpath "$ANDROID_JAR" -d "$temporary/classes" \
    "$source_dir"/src/com/oneplusopen/nhlauncher/*.java
find "$temporary/classes" -type f -name '*.class' >"$temporary/inputs"
"$ANDROID_BUILD_TOOLS/d8" --min-api 26 --lib "$ANDROID_JAR" \
    --output "$temporary/dex" "@$temporary/inputs"
"$ANDROID_BUILD_TOOLS/aapt2" link -I "$ANDROID_JAR" \
    --manifest "$source_dir/AndroidManifest.xml" -o "$temporary/unsigned.apk"
(cd "$temporary/dex" && zip -q "$temporary/unsigned.apk" classes.dex)
"$ANDROID_BUILD_TOOLS/zipalign" -f 4 "$temporary/unsigned.apk" "$temporary/aligned.apk"
"$ANDROID_BUILD_TOOLS/apksigner" sign --ks "$KEYSTORE" --out "$output" "$temporary/aligned.apk"
"$ANDROID_BUILD_TOOLS/apksigner" verify "$output"
