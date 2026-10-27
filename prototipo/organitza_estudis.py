#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_SOURCE = os.path.expanduser("~/Baixades")
DEFAULT_DEST = os.path.expanduser("~/Documents")
CONFIG_FILE = os.path.expanduser("~/.config/organitza_estudis.json")

SUBJECT_FOLDERS = {
    "Bases de dades": ["bases dades", "bbdd", "sql", "mysql", "postgres", "base dades", "entitats", "atributs", "erd", "model relacional", "clau primària", "relació"],
    "Entorns de desenrotllament": ["entorns", "desenvolupament", "edi", "ide", "git", "github", "commit", "branch", "versionat", "docker", "repositori"],
    "Llenguatge_de_marques": ["llenguatge de marques", "html", "css", "xml", "xsd", "xsl", "marques", "etiqueta"],
    "Programació": ["programació", "python", "java", "pseudocodi", "algoritme", "bucles", "funcions", "if", "for", "while"],
    "Projecte intermodular": ["projecte intermodular", "projecte", "intermodular"],
    "Sistemes informàtics": ["sistemes informàtics", "sistemes", "so", "linux", "windows", "xarxes", "maquinari", "virtualització", "terminal", "fitxers"],
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"keywords": SUBJECT_FOLDERS}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"Configuració guardada a {CONFIG_FILE}")

def classify_from_text(text, keywords):
    text_lower = text.lower()
    for subject, kws in keywords.items():
        for kw in kws:
            if kw.lower() in text_lower:
                return subject
    return None

def generate_md_from_pdf(pdf_path, md_path, max_pages=2):
    """Generate a summary .md by reading only first N pages using pdftotext."""
    try:
        # pdftotext -f 1 -l max_pages pdf - 
        result = subprocess.run(
            ['pdftotext', '-f', '1', '-l', str(max_pages), str(pdf_path), '-'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        text = result.stdout.decode('utf-8', errors='ignore')
        if not text.strip():
            return False
        # Create concise MD with extracted content for classification
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Auto-resum: {Path(pdf_path).name}\n\n")
            f.write("## Contingut extret (primeres pàgines)\n\n")
            f.write(text.strip()[:8000])  # limit to avoid huge files
            f.write("\n")
        return True
    except FileNotFoundError:
        print("Error: pdftotext no trobat. Instal·la poppler-utils.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error generant MD des de PDF: {e}", file=sys.stderr)
        return False

def find_existing_md(file_path):
    p = Path(file_path)
    base = p.stem
    parent = p.parent
    md_candidate = parent / f"{base}.md"
    if md_candidate.exists():
        return md_candidate
    for f in parent.iterdir():
        if f.is_file() and f.suffix.lower() == '.md' and f.stem.lower() == base.lower():
            return f
    return None

def organize_files(source_dir, dest_dir, keywords, dry_run=False, auto_generate=True, max_pages=2):
    source = Path(source_dir)
    dest = Path(dest_dir)
    
    if not source.exists():
        print(f"Error: No existeix el directori origen {source}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Escanejant {source} (auto-generació: {'sí' if auto_generate else 'no'})...")
    moved = 0
    
    for item in source.iterdir():
        if item.is_dir():
            continue
        if item.suffix.lower() == '.md':
            continue
        
        md_file = find_existing_md(item)
        generated = False
        
        # Auto-generate MD from PDF if missing
        if not md_file and auto_generate and item.suffix.lower() == '.pdf':
            md_file = item.parent / f"{item.stem}.md"
            if dry_run:
                print(f"[DRY-RUN] Generaria {md_file.name} des de {item.name} (pàgines 1-{max_pages})")
                # Try to generate anyway for classification in dry-run? better generate temp
                if generate_md_from_pdf(item, md_file, max_pages):
                    generated = True
                else:
                    print(f"❌ No s'ha pogut generar MD per {item.name}")
                    continue
            else:
                if generate_md_from_pdf(item, md_file, max_pages):
                    generated = True
                    print(f"📝 Generat {md_file.name} des de {item.name} (primeres {max_pages} pàgines)")
                else:
                    print(f"❌ No s'ha pogut generar MD per {item.name}")
                    continue
        elif not md_file:
            print(f"⚠️  Sense .md associat: {item.name} (saltat)")
            continue
        
        # Classify from MD content
        try:
            with open(md_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"Error llegint {md_file}: {e}", file=sys.stderr)
            continue
        
        subject = classify_from_text(content, keywords)
        if not subject:
            print(f"❓ No s'ha pogut classificar {item.name} (revisar contingut de {md_file.name})")
            continue
        
        target_dir = dest / subject
        if not target_dir.exists():
            print(f"Error: No existeix el directori destí {target_dir}", file=sys.stderr)
            continue
        
        target_path = target_dir / item.name
        if dry_run:
            print(f"[DRY-RUN] Moure {item.name} -> {subject}/ ({md_file.name})")
            if generated and not dry_run:  # won't happen
                pass
        else:
            try:
                counter = 1
                orig_target = target_path
                while target_path.exists():
                    stem = orig_target.stem
                    suffix = orig_target.suffix
                    target_path = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                shutil.move(str(item), str(target_path))
                print(f"✓ {item.name} -> {subject}/")
                md_target = target_dir / md_file.name
                if md_target.exists():
                    # avoid overwrite
                    if md_target.stat().st_size != md_file.stat().st_size:
                        c = 1
                        base_m = md_target.stem
                        ext_m = md_target.suffix
                        while md_target.exists():
                            md_target = target_dir / f"{base_m}_{c}{ext_m}"
                            c += 1
                shutil.move(str(md_file), str(md_target))
                print(f"  + {md_file.name} -> {subject}/")
                moved += 1
            except Exception as e:
                print(f"Error movent {item.name}: {e}", file=sys.stderr)
    
    if not dry_run:
        print(f"\n{moved} fitxer(s) organitzat(s).")
    else:
        print(f"\n[DRY-RUN] Simulació completada.")

def main():
    parser = argparse.ArgumentParser(
        description="Organitza fitxers d'estudi de Baixades a Documents (auto-genera .md des de PDFs)",
        epilog="Llegeix només les primeres pàgines amb pdftotext - no carrega el PDF sencer"
    )
    parser.add_argument('-s', '--source', default=DEFAULT_SOURCE)
    parser.add_argument('-d', '--dest', default=DEFAULT_DEST)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-auto', action='store_true', help="No generar .md automàticament")
    parser.add_argument('--pages', type=int, default=2, help="Pàgines a extreure (per defecte: 2)")
    parser.add_argument('--show-config', action='store_true')
    parser.add_argument('--init-config', action='store_true')
    
    args = parser.parse_args()
    
    config = load_config()
    keywords = config.get("keywords", SUBJECT_FOLDERS)
    
    if args.show_config:
        print(json.dumps(keywords, ensure_ascii=False, indent=2))
        return
    if args.init_config:
        save_config({"keywords": SUBJECT_FOLDERS})
        return
    
    organize_files(args.source, args.dest, keywords, args.dry_run, auto_generate=not args.no_auto, max_pages=args.pages)

if __name__ == '__main__':
    main()
