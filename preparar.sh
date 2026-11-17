#!/usr/bin/env bash
# Build the Linux x86-64 engine locally from Johann Ruiz's published recompilation.
set -euo pipefail
cd -- "$(dirname -- "$0")"
test "$(uname -m)" = x86_64
if [[ ! -s roms/dayto2pe.zip ]]; then
  echo "Place your complete dayto2pe.zip in roms/ before building." >&2
  exit 1
fi
revision=1adde5b41d6a7bab47a8a0b003557298a259e62c
base=https://raw.githubusercontent.com/johannruiz/daytona-usa-2-web/$revision
mkdir -p upstream/shaders upstream/licenses build vendor
for item in daytona2.wasm nvram.js LICENSE NOTICE shaders/{compose,r3d}.wgsl licenses/{LostWorldNative-MIT,MAME-315-5881-BSD-3-Clause,Musashi-LICENSE,PL_MPEG-MIT,SoftFloat-README,mame_m3comm_BSD-3-Clause,miniz-MIT,model3recomp-MIT,model3recomp-THIRD_PARTY}.txt; do
  curl -fsSL --retry 2 "$base/$item" -o "upstream/$item.tmp"
  mv "upstream/$item.tmp" "upstream/$item"
done
python3 -m pip install --disable-pip-version-check --target vendor 'wasmtime==50.0.1' 'wgpu==0.33.0' 'PySDL2==0.9.17'
if ! PYTHONPATH=vendor python3 -c 'from PIL import Image, ImageDraw, ImageFont' 2>/dev/null; then
  python3 -m pip install --disable-pip-version-check --target vendor 'Pillow>=10.1'
fi
tool=build/binaryen-version_133/bin/wasm-opt
if [[ ! -x "$tool" ]]; then
  url=https://github.com/WebAssembly/binaryen/releases/download/version_133/binaryen-version_133-x86_64-linux.tar.gz
  curl -fsSL --retry 2 "$url" -o build/binaryen.tar.gz
  digest=$(curl -fsSL "$url.sha256" | cut -d' ' -f1)
  echo "$digest  build/binaryen.tar.gz" | sha256sum -c -
  tar xzf build/binaryen.tar.gz -C build binaryen-version_133/bin/wasm-opt
fi
"$tool" --all-features --disable-compact-imports --emit-exnref upstream/daytona2.wasm -o build/daytona2.eh.wasm
PYTHONPATH="$PWD/vendor" python3 src/compile_game.py
