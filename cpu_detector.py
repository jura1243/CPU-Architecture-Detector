import os
import platform
import re
import subprocess

def detect_cpu_architecture():
    """Определяет архитектуру процессора с детализацией версий x86-64 и AMD Zen"""
    # Проверка для Linux через /proc/cpuinfo
    if os.path.exists('/proc/cpuinfo'):
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
            
            # Сбор данных из cpuinfo
            vendor_id = re.search(r'^\s*vendor_id\s*:\s*(\S+)', cpuinfo, re.MULTILINE | re.IGNORECASE)
            vendor_id = vendor_id.group(1).lower() if vendor_id else ''
            
            flags_match = re.search(r'^\s*flags\s*:\s*(.*)', cpuinfo, re.MULTILINE | re.IGNORECASE)
            flags = set(re.split(r'\s+', flags_match.group(1).strip().lower())) if flags_match else set()
            
            family_match = re.search(r'^\s*cpu\s+family\s*:\s*(\d+)', cpuinfo, re.MULTILINE | re.IGNORECASE)
            family = int(family_match.group(1)) if family_match else None
            
            model_match = re.search(r'^\s*model\s*:\s*(\d+)', cpuinfo, re.MULTILINE | re.IGNORECASE)
            model = int(model_match.group(1)) if model_match else None
            
            # RISC-V (проверка по ISA)
            if re.search(r'^\s*isa\s*:\s*rv', cpuinfo, re.MULTILINE | re.IGNORECASE):
                return 'risc-v'
            
            # ARM64 (ARMv8)
            if re.search(r'^\s*(?:cpu\s+)?architecture\s*:\s*8\b', cpuinfo, re.MULTILINE | re.IGNORECASE):
                return 'arm64'
            
            # ARM32 (ARMv7 и ниже)
            if re.search(r'^\s*(?:cpu\s+)?architecture\s*:\s*[0-7]\b', cpuinfo, re.MULTILINE | re.IGNORECASE):
                return 'arm32'
            
            # x86_64 (наличие флага lm = long mode)
            if 'lm' in flags and ('vendor_id' in cpuinfo.lower() or 'cpu family' in cpuinfo.lower()):
                # Определение версии x86-64
                x86_version = None
                
                # Проверка x86-64-v2: CMPXCHG16B, LAHF/SAHF, POPCNT, SSE3/SSSE3, SSE4.1, SSE4.2
                # Учитываем, что SSSE3 может быть вместо SSE3
                v2_mandatory = ['cx16', 'lahf_lm', 'popcnt', 'sse4_1', 'sse4_2']
                v2_sse_check = 'sse3' in flags or 'ssse3' in flags
                if all(flag in flags for flag in v2_mandatory) and v2_sse_check:
                    x86_version = 'v2'
                    
                    # Проверка x86-64-v3: AVX, AVX2, BMI1, BMI2, F16C, FMA, MOVBE, XSAVE
                    # LZCNT не обязательна для v3 (Intel не всегда поддерживает)
                    v3_core = ['avx', 'avx2', 'bmi1', 'bmi2', 'f16c', 'fma', 'movbe', 'xsave']
                    if all(flag in flags for flag in v3_core):
                        x86_version = 'v3'
                        
                        # Проверка x86-64-v4: AVX512F, AVX512BW, AVX512DQ, AVX512VL
                        v4_flags = ['avx512f', 'avx512bw', 'avx512dq', 'avx512vl']
                        if all(flag in flags for flag in v4_flags):
                            x86_version = 'v4'
                
                # Определение поколения AMD Zen (только для AMD)
                amd_zen = None
                if 'amd' in vendor_id and family == 25:
                    # Zen 3: модели 68 (Vermeer), 94 (Cezanne)
                    if model in [68, 94]:
                        amd_zen = 'Zen 3'
                    # Zen 4: модели 17 (Raphael), 33 (Phoenix)
                    elif model in [17, 33]:
                        amd_zen = 'Zen 4'
                
                # Формирование результата
                result = 'x86_64'
                if x86_version:
                    result += f'-{x86_version}'
                if amd_zen:
                    result += f' ({amd_zen})'
                return result
            
            # x86 (32-bit)
            if 'vendor_id' in cpuinfo.lower() and 'lm' not in flags:
                return 'x86'
            
            # Эльбрус (e2k)
            if any(kw in cpuinfo.lower() for kw in ['mcst', 'e2k', 'loongson']):
                return 'e2k'
            
            # PowerPC
            if any(kw in cpuinfo.lower() for kw in ['power', 'ppc']):
                return 'powerpc'
            
            # m68k
            if 'm68k' in cpuinfo.lower():
                return 'm68k'
            
            # SPARC
            if 'sparc' in cpuinfo.lower():
                return 'SPARC'
            
            # Alpha
            if 'alpha' in cpuinfo.lower():
                return 'Alpha'
            
            # LoongArch
            if 'loongarch' in cpuinfo.lower():
                return 'Loongson'

        except Exception as e:
            print(f"Warning: Error reading /proc/cpuinfo: {e}")

    # Кросс-платформенная проверка через platform
    machine = platform.machine().lower()
    
    # Сопоставление с известными архитектурами
    if machine in ('x86_64', 'amd64'):
        return 'x86_64'
    elif machine in ('i386', 'i686', 'x86'):
        return 'x86'
    elif machine in ('aarch64', 'arm64', 'armv8'):
        return 'arm64'
    elif machine.startswith(('armv', 'arm')):
        return 'arm32'
    elif machine in ('riscv64', 'riscv32'):
        return 'risc-v'
    elif machine in ('ppc', 'ppc64', 'ppc64le'):
        return 'powerpc'
    elif machine == 'm68k':
        return 'm68k'
    elif machine.startswith('sparc'):
        return 'SPARC'
    elif machine == 'alpha':
        return 'Alpha'
    elif machine in ('loongarch64', 'loongarch32'):
        return 'Loongson'
    
    # Дополнительные проверки для macOS
    if platform.system() == 'Darwin':
        try:
            # Проверка на Apple Silicon
            if 'arm' in machine or 'aarch64' in machine:
                return 'arm64'
            
            # Проверка через sysctl
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                   capture_output=True, text=True)
            cpu_brand = result.stdout.lower()
            if 'apple' in cpu_brand and ('m1' in cpu_brand or 'm2' in cpu_brand or 'm3' in cpu_brand):
                return 'arm64 (Apple Silicon)'
        except:
            pass
    
    # Дополнительные проверки для Windows
    if platform.system() == 'Windows':
        try:
            # Проверка через wmic
            result = subprocess.run(['wmic', 'cpu', 'get', 'Name'], 
                                  capture_output=True, text=True)
            cpu_name = result.stdout.lower()
            
            # Проверка AMD Zen
            if 'ryzen 5' in cpu_name or 'ryzen 7 5' in cpu_name or 'epyc 7' in cpu_name:
                return 'x86_64-v3 (Zen 3)'
            elif 'ryzen 5 7' in cpu_name or 'ryzen 7 7' in cpu_name or 'epyc 9' in cpu_name:
                return 'x86_64-v4 (Zen 4)'
        except:
            pass

    return 'unknown'

def detailed_x86_info():
    """Выводит детальную информацию о x86 инструкциях для отладки"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
        
        flags_match = re.search(r'^\s*flags\s*:\s*(.*)', cpuinfo, re.MULTILINE | re.IGNORECASE)
        if flags_match:
            flags = set(re.split(r'\s+', flags_match.group(1).strip().lower()))
            
            print("\nRelevant instruction set flags:")
            
            # x86-64-v2 requirements
            v2_mandatory = ['cx16', 'lahf_lm', 'popcnt', 'sse4_1', 'sse4_2']
            v2_sse_present = 'sse3' in flags or 'ssse3' in flags
            v2_status = all(f in flags for f in v2_mandatory) and v2_sse_present
            print(f"x86-64-v2: {'SUPPORTED' if v2_status else 'NOT SUPPORTED'}")
            if not v2_status:
                missing = [f for f in v2_mandatory if f not in flags]
                if not v2_sse_present:
                    missing.append('sse3 or ssse3')
                print(f"  Missing flags: {', '.join(missing)}")
            
            # x86-64-v3 requirements (without LZCNT)
            v3_core = ['avx', 'avx2', 'bmi1', 'bmi2', 'f16c', 'fma', 'movbe', 'xsave']
            v3_status = all(f in flags for f in v3_core)
            print(f"x86-64-v3: {'SUPPORTED' if v3_status else 'NOT SUPPORTED'}")
            if not v3_status:
                missing = [f for f in v3_core if f not in flags]
                print(f"  Missing flags: {', '.join(missing)}")
            
            # x86-64-v4 requirements
            v4_flags = ['avx512f', 'avx512bw', 'avx512dq', 'avx512vl']
            v4_status = all(f in flags for f in v4_flags)
            print(f"x86-64-v4: {'SUPPORTED' if v4_status else 'NOT SUPPORTED'}")
            if not v4_status:
                missing = [f for f in v4_flags if f not in flags]
                print(f"  Missing flags: {', '.join(missing)}")
                
            # Дополнительно показываем LZCNT для информации
            lzcnt_status = 'PRESENT' if 'lzcnt' in flags else 'NOT PRESENT'
            print(f"LZCNT (for reference): {lzcnt_status}")
    except:
        pass

if __name__ == "__main__":
    arch = detect_cpu_architecture()
    print(f"Detected CPU architecture: {arch}")
    
    # Дополнительная информация для диагностики
    print("\nDebug info:")
    print(f"Platform machine: {platform.machine()}")
    print(f"Platform architecture: {platform.architecture()}")
    print(f"System: {platform.system()}")
    
    # Детальная информация для x86 систем
    if 'x86_64' in arch:
        detailed_x86_info()