#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_dir="$repo_root/plugins/portfolio-analyser/src/bridge"
bin_dir="$repo_root/plugins/portfolio-analyser/bin"

build() {
  target_os=$1
  target_arch=$2
  target_path=$3
  mkdir -p "$(dirname -- "$target_path")"
  (
    cd "$source_dir"
    CGO_ENABLED=0 GOOS="$target_os" GOARCH="$target_arch" \
      go build -buildvcs=false -trimpath -ldflags="-s -w -buildid=" -o "$target_path" .
  )
}

build darwin arm64 "$bin_dir/native/darwin-arm64/portfolio-analyser-bridge"
build darwin amd64 "$bin_dir/native/darwin-amd64/portfolio-analyser-bridge"
build linux arm64 "$bin_dir/native/linux-arm64/portfolio-analyser-bridge"
build linux amd64 "$bin_dir/native/linux-amd64/portfolio-analyser-bridge"
build windows amd64 "$bin_dir/portfolio-analyser-bridge.exe"

chmod +x "$bin_dir/portfolio-analyser-bridge" "$bin_dir"/native/*/portfolio-analyser-bridge
(
  cd "$repo_root/plugins/portfolio-analyser"
  shasum -a 256 \
    bin/portfolio-analyser-bridge.exe \
    bin/native/darwin-amd64/portfolio-analyser-bridge \
    bin/native/darwin-arm64/portfolio-analyser-bridge \
    bin/native/linux-amd64/portfolio-analyser-bridge \
    bin/native/linux-arm64/portfolio-analyser-bridge \
    > checksums.txt
)
