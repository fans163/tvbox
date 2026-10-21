#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TOOLS="${TVBOX_A4_TOOLS:-$ROOT/.tools}"
BUILD="$ROOT/build"
OUT="$ROOT/TVBox-Android4-Spider.jar"

R8_JAR="$TOOLS/r8.jar"
ANDROID_JAR="$TOOLS/android-4.0.1.2.jar"

mkdir -p "$TOOLS"
if [ ! -f "$R8_JAR" ]; then
  echo "下载 d8 (r8.jar)..."
  curl -sSL -o "$R8_JAR" \
    "https://dl.google.com/dl/android/maven2/com/android/tools/r8/8.13.25/r8-8.13.25.jar"
fi
if [ ! -f "$ANDROID_JAR" ]; then
  echo "下载 Android 4.0 (API 14) 编译用 android.jar..."
  curl -sSL -o "$ANDROID_JAR" \
    "https://repo1.maven.org/maven2/com/google/android/android/4.0.1.2/android-4.0.1.2.jar"
fi

rm -rf "$BUILD"
mkdir -p "$BUILD/stubclasses" "$BUILD/classes" "$BUILD/dex"

# 编译 TVBox Spider 存根（只用于编译，不进入最终 jar）
find "$ROOT/stubs" -name '*.java' > "$BUILD/stub-sources.txt"
javac --release 8 -encoding UTF-8 -Xlint:-options \
  -cp "$ANDROID_JAR" -d "$BUILD/stubclasses" @"$BUILD/stub-sources.txt"
jar cf "$BUILD/stubs.jar" -C "$BUILD/stubclasses" .

# 编译 spider 实现
find "$ROOT/src" -name '*.java' > "$BUILD/sources.txt"
javac --release 8 -encoding UTF-8 -Xlint:-options \
  -cp "$BUILD/stubs.jar:$ANDROID_JAR" -d "$BUILD/classes" @"$BUILD/sources.txt"

# 转 dex：min-api 14 -> Android 4.0，输出 dex 035，并做 Java 8 desugar
find "$BUILD/classes" -name '*.class' > "$BUILD/classes.txt"
java -cp "$R8_JAR" com.android.tools.r8.D8 \
  --min-api 14 \
  --lib "$ANDROID_JAR" \
  --lib "$BUILD/stubs.jar" \
  --output "$BUILD/dex" @"$BUILD/classes.txt"

# 打包：classes.dex 必须位于 jar 根目录
rm -f "$OUT"
(cd "$BUILD/dex" && jar cf "$OUT" classes.dex)

echo "已生成: $OUT"
unzip -l "$OUT"
