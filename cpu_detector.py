import os
import platform
import re
import subprocess
import tempfile

def get_cpu_flags_windows():
    """Получает флаги процессора в Windows через WMI"""
    try:
        # Запускаем PowerShell для получения CPU информации
        powershell_cmd = [
            'powershell', 
            '-Command', 
            'Get-WmiObject Win32_Processor | Select-Object Name, Description, Family, Manufacturer'
        ]
        result = subprocess.run(powershell_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            cpu_info = result.stdout.lower()
        else:
            cpu_info = ""
    except:
        cpu_info = ""
    
    # Пытаемся получить флаги через wmic
    try:
        wmic_result = subprocess.run(
            ['wmic', 'cpu', 'get', 'Name,Description'], 
            capture_output=True, text=True, timeout=10
        )
        if wmic_result.returncode == 0:
            cpu_info += wmic_result.stdout.lower()
    except:
        pass
    
    # Получаем флаги через специальный инструмент
    flags = set()
    try:
        # Проверяем наличие CPU-Z или других инструментов
        cpu_tools = [
            ['cpuz', '/cmd=getfeatures'],
            ['coreinfo', '-n'],  # Sysinternals
        ]
        
        for tool in cpu_tools:
            try:
                result = subprocess.run(tool, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    flags.update(extract_flags_from_text(result.stdout.lower()))
                    break
            except:
                continue
    except:
        pass
    
    # Если инструменты недоступны, пытаемся получить флаги через CPUID напрямую
    try:
        flags.update(get_cpuid_flags_windows())
    except:
        pass
    
    # Добавляем флаги на основе названия процессора
    flags.update(infer_flags_from_name(cpu_info))
    
    return flags, cpu_info

def extract_flags_from_text(text):
    """Извлекает флаги из текста (для CPU-Z и аналогов)"""
    flags = set()
    # Поиск известных флагов в тексте
    patterns = [
        r'avx512[^\s,;.)]+',  # avx512f, avx512bw, etc.
        r'avx\d*',             # avx, avx2
        r'sse\d*[a-z]*',       # sse, sse2, sse3, ssse3, sse4_1, sse4_2
        r'bmi\d?',             # bmi1, bmi2
        r'fma',                # fma
        r'f16c',               # f16c
        r'movbe',              # movbe
        r'xsave',              # xsave
        r'cx16',               # cx16
        r'lahf',               # lahf_lm
        r'popcnt',             # popcnt
        r'lzcnt',              # lzcnt
        r'tbm',                # tbm
        r'abm',                # abm
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            flags.add(match.replace('.', '_').replace('-', '_'))
    
    return flags

def get_cpuid_flags_windows():
    """Получает флаги через CPUID на Windows (через встроенный код)"""
    flags = set()
    
    # Для Windows создаем временный C-файл для получения CPUID
    try:
        c_code = """
#include <stdio.h>
#include <string.h>

#ifdef _MSC_VER
    #include <intrin.h>
    void cpuid(int info[4], int level) {
        __cpuid(info, level);
    }
#else
    #include <cpuid.h>
    void cpuid(int info[4], int level) {
        __cpuid_count(level, 0, info[0], info[1], info[2], info[3]);
    }
#endif

int main() {
    int cpuinfo[4] = {0};
    
    // Standard function 1
    cpuid(cpuinfo, 1);
    unsigned int ecx = cpuinfo[2];
    unsigned int edx = cpuinfo[3];
    
    // Extended function 7
    cpuid(cpuinfo, 7);
    unsigned int ebx = cpuinfo[1];
    
    // Extended function 0x80000001
    cpuid(cpuinfo, 0x80000001);
    unsigned int ext_ecx = cpuinfo[2];
    unsigned int ext_edx = cpuinfo[3];
    
    // Print flags based on bit positions
    if (edx & (1 << 15)) printf("cmov ");
    if (edx & (1 << 23)) printf("mmx ");
    if (edx & (1 << 25)) printf("sse ");
    if (edx & (1 << 26)) printf("sse2 ");
    if (ecx & (1 << 0)) printf("sse3 ");
    if (ecx & (1 << 9)) printf("ssse3 ");
    if (ecx & (1 << 19)) printf("sse4_1 ");
    if (ecx & (1 << 20)) printf("sse4_2 ");
    if (ecx & (1 << 28)) printf("avx ");
    if (ecx & (1 << 15)) printf("cx16 ");
    if (ecx & (1 << 29)) printf("f16c ");
    if (ecx & (1 << 12)) printf("fma ");
    if (ecx & (1 << 5)) printf("abm ");
    if (ecx & (1 << 22)) printf("movbe ");
    if (ecx & (1 << 27)) printf("xsave ");
    if (ecx & (1 << 23)) printf("popcnt ");
    if (edx & (1 << 29)) printf("lahf_lm ");
    
    if (ebx & (1 << 3)) printf("bmi1 ");
    if (ebx & (1 << 8)) printf("bmi2 ");
    if (ebx & (1 << 5)) printf("avx2 ");
    
    if (ext_ecx & (1 << 5)) printf("lzcnt ");
    if (ext_ecx & (1 << 21)) printf("tbm ");
    
    // AVX-512 flags (ebx bits 16-31 when calling with ECX=0)
    cpuid(cpuinfo, 7);
    if (cpuinfo[1] & (1 << 16)) printf("avx512f ");
    if (cpuinfo[1] & (1 << 17)) printf("avx512dq ");
    if (cpuinfo[1] & (1 << 28)) printf("avx512cd ");
    if (cpuinfo[1] & (1 << 30)) printf("avx512bw ");
    if (cpuinfo[1] & (1 << 31)) printf("avx512vl ");
    
    return 0;
}
"""
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(c_code)
            temp_c_file = f.name
        
        temp_exe_file = temp_c_file.replace('.c', '.exe')
        
        # Компилируем (пытаемся с разными компиляторами)
        compilers = [
            ['gcc', temp_c_file, '-o', temp_exe_file],
            ['clang', temp_c_file, '-o', temp_exe_file],
            ['cl', temp_c_file]  # MSVC (выходной файл будет .obj -> .exe)
        ]
        
        compiled = False
        for compiler in compilers:
            try:
                result = subprocess.run(compiler, capture_output=True, timeout=10)
                if result.returncode == 0:
                    compiled = True
                    break
            except:
                continue
        
        if compiled:
            # Запускаем скомпилированную программу
            exe_path = temp_exe_file if os.path.exists(temp_exe_file) else temp_c_file.replace('.c', '.exe')
            if os.path.exists(exe_path):
                try:
                    result = subprocess.run([exe_path], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        cpuid_flags = result.stdout.strip().split()
                        flags.update(cpuid_flags)
                except:
                    pass
            
            # Удаляем временные файлы
            try:
                os.unlink(temp_c_file)
                if os.path.exists(temp_exe_file):
                    os.unlink(temp_exe_file)
                obj_file = temp_c_file.replace('.c', '.obj')
                if os.path.exists(obj_file):
                    os.unlink(obj_file)
            except:
                pass
    
    except:
        pass
    
    return flags

def infer_flags_from_name(cpu_name):
    """Определяет флаги на основе названия процессора"""
    flags = set()
    
    cpu_name_lower = cpu_name.lower()
    
    # Intel поколения
    if any(gen in cpu_name_lower for gen in ['core i3', 'core i5', 'core i7', 'core i9']):
        # 10th gen и выше (Ice Lake) - AVX-512
        if any(year in cpu_name_lower for year in ['10', '11', '12', '13', '14', '15']):
            flags.update(['avx', 'avx2', 'fma', 'bmi1', 'bmi2'])
            if any(avx512 in cpu_name_lower for avx512 in ['xeon', 'h', 'hk', 'hx']):
                flags.update(['avx512f', 'avx512bw', 'avx512dq', 'avx512vl'])
        # 8th-9th gen (Coffee Lake) - AVX2
        elif any(year in cpu_name_lower for year in ['8', '9']):
            flags.update(['avx', 'avx2', 'fma', 'bmi1', 'bmi2'])
        # 6th-7th gen (Skylake) - AVX2
        else:
            flags.update(['avx', 'avx2', 'fma', 'bmi1', 'bmi2'])
    
    # AMD поколения
    if 'ryzen' in cpu_name_lower:
        if '5' in cpu_name_lower and any(word in cpu_name_lower for word in ['5000', 'threadripper']):
            flags.update(['avx', 'avx2', 'fma', 'bmi1', 'bmi2', 'lzcnt'])
        elif '7' in cpu_name_lower and any(word in cpu_name_lower for word in ['7000', 'threadripper']):
            flags.update(['avx', 'avx2', 'fma', 'bmi1', 'bmi2', 'lzcnt', 'avx512f'])
    
    # Добавляем общие флаги для современных процессоров
    flags.update(['sse3', 'ssse3', 'sse4_1', 'sse4_2', 'cx16', 'lahf_lm', 'popcnt', 'xsave'])
    
    return flags

def detect_cpu_architecture():
    """Определяет архитектуру процессора с детализацией версий x86-64 и AMD Zen"""
    
    system = platform.system().lower()
    
    if system == 'linux' and os.path.exists('/proc/cpuinfo'):
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
                v2_mandatory = ['cx16', 'lahf_lm', 'popcnt', 'sse4_1', 'sse4_2']
                v2_sse_check = 'sse3' in flags or 'ssse3' in flags
                if all(flag in flags for flag in v2_mandatory) and v2_sse_check:
                    x86_version = 'v2'
                    
                    # Проверка x86-64-v3: AVX, AVX2, BMI1, BMI2, F16C, FMA, MOVBE, XSAVE
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

    elif system == 'windows':
        # Получаем флаги для Windows
        windows_flags, cpu_info = get_cpu_flags_windows()
        
        if windows_flags:
            # Проверяем x86_64
            if 'lm' in windows_flags or any(f in windows_flags for f in ['avx', 'avx2', 'sse4_1']):
                # Определение версии x86-64
                x86_version = None
                
                # Проверка x86-64-v2: CMPXCHG16B, LAHF/SAHF, POPCNT, SSE3/SSSE3, SSE4.1, SSE4.2
                v2_mandatory = ['cx16', 'lahf_lm', 'popcnt', 'sse4_1', 'sse4_2']
                v2_sse_check = 'sse3' in windows_flags or 'ssse3' in windows_flags
                if all(flag in windows_flags for flag in v2_mandatory) and v2_sse_check:
                    x86_version = 'v2'
                    
                    # Проверка x86-64-v3: AVX, AVX2, BMI1, BMI2, F16C, FMA, MOVBE, XSAVE
                    v3_core = ['avx', 'avx2', 'bmi1', 'bmi2', 'f16c', 'fma', 'movbe', 'xsave']
                    if all(flag in windows_flags for flag in v3_core):
                        x86_version = 'v3'
                        
                        # Проверка x86-64-v4: AVX512F, AVX512BW, AVX512DQ, AVX512VL
                        v4_flags = ['avx512f', 'avx512bw', 'avx512dq', 'avx512vl']
                        if all(flag in windows_flags for flag in v4_flags):
                            x86_version = 'v4'
                
                # Определение поколения AMD Zen через название процессора
                amd_zen = None
                if 'amd' in cpu_info:
                    if any(keyword in cpu_info for keyword in ['ryzen 5000', 'threadripper pro 5000', 'epyc milan']):
                        amd_zen = 'Zen 3'
                    elif any(keyword in cpu_info for keyword in ['ryzen 7000', 'threadripper 7000', 'epyc genoa']):
                        amd_zen = 'Zen 4'
                
                # Формирование результата
                result = 'x86_64'
                if x86_version:
                    result += f'-{x86_version}'
                if amd_zen:
                    result += f' ({amd_zen})'
                return result
            elif any(f in windows_flags for f in ['sse', 'sse2']):
                return 'x86'

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

    return 'unknown'

def detailed_x86_info():
    """Выводит детальную информацию о x86 инструкциях для отладки"""
    system = platform.system().lower()
    
    if system == 'linux' and os.path.exists('/proc/cpuinfo'):
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
                
                # x86-64-v3 requirements
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
        except:
            pass
    elif system == 'windows':
        try:
            windows_flags, cpu_info = get_cpu_flags_windows()
            if windows_flags:
                print("\nRelevant instruction set flags:")
                
                # x86-64-v2 requirements
                v2_mandatory = ['cx16', 'lahf_lm', 'popcnt', 'sse4_1', 'sse4_2']
                v2_sse_present = 'sse3' in windows_flags or 'ssse3' in windows_flags
                v2_status = all(f in windows_flags for f in v2_mandatory) and v2_sse_present
                print(f"x86-64-v2: {'SUPPORTED' if v2_status else 'NOT SUPPORTED'}")
                if not v2_status:
                    missing = [f for f in v2_mandatory if f not in windows_flags]
                    if not v2_sse_present:
                        missing.append('sse3 or ssse3')
                    print(f"  Missing flags: {', '.join(missing)}")
                
                # x86-64-v3 requirements
                v3_core = ['avx', 'avx2', 'bmi1', 'bmi2', 'f16c', 'fma', 'movbe', 'xsave']
                v3_status = all(f in windows_flags for f in v3_core)
                print(f"x86-64-v3: {'SUPPORTED' if v3_status else 'NOT SUPPORTED'}")
                if not v3_status:
                    missing = [f for f in v3_core if f not in windows_flags]
                    print(f"  Missing flags: {', '.join(missing)}")
                
                # x86-64-v4 requirements
                v4_flags = ['avx512f', 'avx512bw', 'avx512dq', 'avx512vl']
                v4_status = all(f in windows_flags for f in v4_flags)
                print(f"x86-64-v4: {'SUPPORTED' if v4_status else 'NOT SUPPORTED'}")
                if not v4_status:
                    missing = [f for f in v4_flags if f not in windows_flags]
                    print(f"  Missing flags: {', '.join(missing)}")
        except:
            print("\nCould not retrieve detailed CPU flags on Windows")

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