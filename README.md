# CPU Architecture Detector

Python script that detects CPU architecture by checking for specific instruction sets and system characteristics. Supports detailed detection of x86-64 versions (v2, v3, v4) and AMD Zen generations (3, 4).

## Features

- **Multi-architecture support**: Detects x86, x86_64, ARM32, ARM64, RISC-V, e2k (Elbrus), PowerPC, m68k, SPARC, Alpha, Loongson
- **x86-64 version detection**: Identifies v2, v3, v4 compatibility levels
- **AMD Zen detection**: Recognizes Zen 3 and Zen 4 generations
- **Cross-platform**: Works on Linux, Windows, macOS
- **No external dependencies**: Uses only built-in Python modules
- **Detailed diagnostics**: Shows missing/supported instruction sets for debugging

## Supported Architectures

| Architecture | Variants |
|--------------|----------|
| x86 | 32-bit |
| x86_64 | v2, v3, v4 (with AMD Zen detection) |
| ARM | 32-bit, 64-bit (ARMv8) |
| RISC-V | 32/64-bit |
| e2k | Elbrus |
| PowerPC | All variants |
| Others | m68k, SPARC, Alpha, Loongson |

## x86-64 Version Requirements

- **v2**: `cx16`, `lahf_lm`, `popcnt`, `sse3/ssse3`, `sse4_1`, `sse4_2`
- **v3**: All v2 + `avx`, `avx2`, `bmi1`, `bmi2`, `f16c`, `fma`, `movbe`, `xsave` *(LZCNT optional)*
- **v4**: All v3 + `avx512f`, `avx512bw`, `avx512dq`, `avx512vl`

## Installation & Usage

```bash
# Clone repository
git clone https://github.com/jura1243/CPU-Architecture-Detector.git
cd CPU-Architecture-Detector

# Run detector
python3 ./cpu_detector.py
```

## Output Examples

```text
# AMD Ryzen 5000 series
Detected CPU architecture: x86_64-v3 (Zen 3)

# Intel Core 14th gen
Detected CPU architecture: x86_64-v3

# ARM64
Detected CPU architecture: arm64
```

## Requirements

- Python 3.x
- Linux: Access to `/proc/cpuinfo`
- Windows: `wmic` command access
- macOS: `sysctl` command access

## License

MIT
