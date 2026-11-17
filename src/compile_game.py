from pathlib import Path
import wasmtime as wt

root = Path(__file__).resolve().parents[1]
config = wt.Config()
config.wasm_exceptions = True
engine = wt.Engine(config)
game = wt.Module.from_file(engine, str(root / "build/daytona2.eh.wasm"))
out = root / "daytona2.x86_64.cwasm"
out.write_bytes(game.serialize())
print("x86-64 AOT output:", out.stat().st_size, flush=True)
