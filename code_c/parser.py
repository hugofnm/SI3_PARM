import re
import os

Conditions = {
    "eq": "0000", "ne": "0001", "cs": "0010", "hs": "0010",
    "cc": "0011", "lo": "0011", "mi": "0100", "pl": "0101",
    "vs": "0110", "vc": "0111", "hi": "1000", "ls": "1001",
    "ge": "1010", "lt": "1011", "gt": "1100", "le": "1101",
    "al": "1110"
}

Instruction = {
    # Format : [Mnémonique, Opcode_Bin, [Tailles Bits], Scale_Immediate(Boolean)]
    
    # SHIFT (Machine: Imm5, Rm, Rd)
    "LSL_IMM"   : ["lsl", "00000",      [5, 3, 3], False], 
    "LSR_IMM"   : ["lsr", "00001",      [5, 3, 3], False],
    "ASR_IMM"   : ["asr", "00010",      [5, 3, 3], False],

    # ADD/SUB REGISTRE (Machine: Rm, Rn, Rd)
    "ADD_REG"   : ["add", "0001100",    [3, 3, 3], False],
    "SUB_REG"   : ["sub", "0001101",    [3, 3, 3], False],

    # ADD/SUB IMM 3-bits (Machine: Imm3, Rn, Rd)
    "ADD_IMM_T1": ["add", "0001110",    [3, 3, 3], False],
    "SUB_IMM_T1": ["sub", "0001111",    [3, 3, 3], False],

    # MOV/CMP/ADD/SUB IMM 8-bits (Machine: Rd, Imm8)
    "MOV_IMM"   : ["mov", "00100",      [3, 8], False],
    "CMP_IMM"   : ["cmp", "00101",      [3, 8], False],
    "ADD_IMM_T2": ["add", "00110",      [3, 8], False],
    "SUB_IMM_T2": ["sub", "00111",      [3, 8], False],

    # ALU (Machine: Rm, Rdn)
    "AND_REG"   : ["and", "0100000000", [3, 3], False],
    "EOR_REG"   : ["eor", "0100000001", [3, 3], False],
    "LSL_REG"   : ["lsl", "0100000010", [3, 3], False],
    "LSR_REG"   : ["lsr", "0100000011", [3, 3], False],
    "ASR_REG"   : ["asr", "0100000100", [3, 3], False],
    "ADC_REG"   : ["adc", "0100000101", [3, 3], False],
    "SBC_REG"   : ["sbc", "0100000110", [3, 3], False],
    "ROR_REG"   : ["ror", "0100000111", [3, 3], False],
    "TST_REG"   : ["tst", "0100001000", [3, 3], False],
    "RSB_REG"   : ["rsb", "0100001001", [3, 3], False],
    "CMP_REG"   : ["cmp", "0100001010", [3, 3], False],
    "CMN_REG"   : ["cmn", "0100001011", [3, 3], False],
    "ORR_REG"   : ["orr", "0100001100", [3, 3], False],
    "MUL"       : ["mul", "0100001101", [3, 3], False],
    "BIC_REG"   : ["bic", "0100001110", [3, 3], False],
    "MVN_REG"   : ["mvn", "0100001111", [3, 3], False],
    "NEGS_REG"  : ["rsb", "0100001001", [3, 3], False],

    # SP RELATIVE (Machine: Rd, Imm8)
    "STR_SP"    : ["str", "10010",      [3, 8], True], 
    "LDR_SP"    : ["ldr", "10011",      [3, 8], True],

    # ADD/SUB SP (Machine: Imm7)
    "ADD_SP_IMM": ["add", "101100000",  [7],    True],   
    "SUB_SP_IMM": ["sub", "101100001",  [7],    True],
}


def binaire_hexa(bin):
    val = hex(int(bin, 2))[2:]
    return val.zfill(4) 

def registre_vers_binaire(nom_reg, bit, scale_by_4=False):
    nom_reg = nom_reg.lower().strip()
    val = 0

    if nom_reg == "sp": val = 13
    elif nom_reg == "lr": val = 14
    elif nom_reg == "pc": val = 15
    elif nom_reg.startswith("r"): val = int(nom_reg[1:])
    elif nom_reg.startswith("#"): 
        val = int(nom_reg.replace("#", ""))
        if scale_by_4:
            val = val // 4
        
    mask = (1 << bit) - 1
    return format(val & mask, f'0{bit}b')

def normalize_instruction(line):
    line = line.lower().strip()
    line = line.replace('[', '').replace(']', '')

    is_branch = line.startswith('b') and not line.startswith('bic')

    if not is_branch:
        regex_op = r'^(mov|add|sub|lsl|lsr|asr|ldr|str|mul|and|orr|eor|rsb|adc|sbc|ror|tst|bic|mvn|cmp|cmn|neg)s\s'
        line = re.sub(regex_op, r'\1 ', line)

    parts = line.split(maxsplit=1)
    name = parts[0]
    args = [a.strip() for a in parts[1].split(',')] if len(parts) > 1 else []
    
    if name == 'mov' and len(args) == 2 and not args[1].startswith('#'):
        name = 'lsl'
        args.append('#0')

    if name == 'mul' and len(args) == 3:
        args = [args[0], args[1]]

    if name == 'rsb' and len(args) == 3 and args[2] == '#0':
        args = [args[1], args[0]]

    if name == 'neg':
        name = 'rsb'

    return name, args

def reorder_args_for_machine(cle, args):
    if cle in ["ADD_REG", "SUB_REG"]:
        if len(args) == 3: return [args[2], args[1], args[0]]
        else: return [args[1], args[0], args[0]]
        
    elif cle in ["LSL_IMM", "LSR_IMM", "ASR_IMM"]:
        return [args[2], args[1], args[0]]
        
    elif cle in ["ADD_IMM_T1", "SUB_IMM_T1"]:
        return [args[2], args[1], args[0]]
    
    alu_2_ops = [
        "CMP_REG", "MUL", "LSL_REG", "LSR_REG", "ASR_REG", 
        "ORR_REG", "EOR_REG", "AND_REG", "ADC_REG", "SBC_REG", 
        "ROR_REG", "BIC_REG", "MVN_REG", "TST_REG", "CMN_REG", 
        "RSB_REG", "NEGS_REG"
    ]
    
    if cle in alu_2_ops:
        if len(args) >= 2:
            return [args[1], args[0]]
        
    return args

def first_pass_scan(raw_content):
    labels = {}
    instructions = []
    pc = 0
    
    lines = [l.strip() for l in raw_content.split('\n') if l.strip()]
    
    for line in lines:
        line = line.lower()

        if (line.startswith('.') or line.startswith('@')) and not ':' in line: 
            continue

        if line.startswith('push') or (line.startswith('add') and 'r7' in line and 'sp' in line):
            continue

        while ':' in line:
            label_part, rest = line.split(':', 1)
            label_name = label_part.strip()
            labels[label_name] = pc
            line = rest.strip()
        
        if line:
            instructions.append((pc, line))
            pc += 1
            
    return labels, instructions

def encode_branch(name, args, current_pc, labels):
    target = args[0]
    if target in labels:
        offset = labels[target] - current_pc - 3
    else:
        offset = -1

    if name == 'b':
        opcode = 0b11100
        mask = (1 << 11) - 1
        bin_val = (opcode << 11) | (offset & mask)
        return hex(bin_val)[2:].zfill(4)
    
    else:
        cond = name[1:]
        if cond in Conditions:
            cond_bits = int(Conditions[cond], 2)
            opcode = 0b1101
            mask = (1 << 8) - 1
            bin_val = (opcode << 12) | (cond_bits << 8) | (offset & mask)
            return hex(bin_val)[2:].zfill(4)
            
    return None

def encode_standard(name, args):
    for cle, val in Instruction.items():
        nom_ref, code_ref, bit_ref, use_scale = val

        if nom_ref == name:
            args_candidats = args[:]

            if "SP" in cle:
                if len(args) == 3 and args[1] == 'sp': args_candidats = [args[0], args[2]]
                elif len(args) == 2 and args[1] == 'sp': args_candidats = [args[0], "#0"]
                elif len(args) == 2 and args[0] == 'sp': args_candidats = [args[1]]
            elif 'sp' in args: 
                continue 

            if len(args_candidats) == len(bit_ref):
                args_ordered = reorder_args_for_machine(cle, args_candidats)
                
                curr_bin = code_ref
                valid = True
                
                for i, taille in enumerate(bit_ref):
                    arg = args_ordered[i]
                    is_imm = arg.startswith('#')
                    
                    if taille == 3 and is_imm and "IMM" not in cle: valid = False; break
                    if "IMM" in cle and not is_imm and taille > 3: valid = False; break
                    
                    curr_bin += registre_vers_binaire(arg, taille, use_scale)
                
                if valid:
                    return binaire_hexa(curr_bin)
    return None

def assemble(content, file):
    # Etape 1 : Scan des labels
    labels, instructions = first_pass_scan(content)
    
    hex_codes = []
    
    
    # Etape 2 : Génération du code
    for pc, line in instructions:
        name, args = normalize_instruction(line)
        
        result_hex = None
        
        # Cas A : C'est une instruction de saut
        if name.startswith('b') and name != 'bic':
            result_hex = encode_branch(name, args, pc, labels)
            
        # Cas B : C'est une instruction standard
        else:
            result_hex = encode_standard(name, args)
            
        if result_hex:
            hex_codes.append(result_hex)
        else:
            file.write(f"\nErreur sur la ligne : {line}")

    return hex_codes

def open_file(file):
    with open(file, 'r') as f:
        contenu = f.read()
    return contenu

def compare(file, str):
    try:
        with open(file, 'r') as f:
            content_bin = f.read()
        if content_bin.split() == str.split():
            return True
        return False
    except FileNotFoundError:
        return False

def process_all_files(root="."):
    count_ok = 0
    count_total = 0
    file = "parser_result.txt"

    with open(file, "w", encoding="utf-8") as log_file:
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                if filename.endswith(".s"):

                    file_s_path = os.path.join(dirpath, filename)
                    file_bin_path = os.path.join(dirpath, filename.replace(".s", ".bin"))
                    
                    try:
                        if os.path.exists(file_bin_path):
                            count_total += 1

                            log_file.write("\n---------------------------------")
                            log_file.write(f"\nTraitement : {file_s_path}")

                            with open(file_s_path, 'r', encoding="utf-8") as f:
                                content_asm = f.read()

                            codes = assemble(content_asm, log_file)
                            res = "v2.0 raw\n" + " ".join(codes)

                            
                            if compare(file_bin_path, res):
                                log_file.write(f"\nsucces pour {os.path.basename(file_bin_path)}")
                                count_ok += 1
                            else:
                                log_file.write(f"\nEchec pour {os.path.basename(file_bin_path)}")
                        else:
                            log_file.write(f"\npas de fichier bin pour {os.path.basename(file_bin_path)}")
                    except Exception as e:
                        log_file.write("\nError")

        log_file.write(f"\n\n--- Bilan : {count_ok}/{count_total} fichiers corrects ---")

process_all_files(".")