"""
Model İndirme Script'i
----------------------
Belge köşe tespiti için gerekli AI modellerini indirir.
"""

import os
import sys
import urllib.request
from pathlib import Path

MODELS = {
    "mobilenet_corner_detector": {
        # Çalışan HuggingFace URL'si (chwshuang reposu)
        "url": "https://huggingface.co/chwshuang/Stable_diffusion_remove_background_model/resolve/main/u2netp.onnx",
        "filename": "u2netp_document.onnx",
        "size_mb": 4.7,
        "description": "Hafif U2-Net-P modeli (ONNX) - Önerilen",
        "optional": False,
    },
    "u2net_document": {
        # Alternatif: GitHub releases üzerinden
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
        "filename": "u2net_document.onnx",
        "size_mb": 168,  # Gerçek boyut ~167.8 MB
        "description": "Tam U2-Net modeli (ONNX) - Daha yüksek doğruluk",
        "optional": True,
    }
}

MODELS_DIR = Path(__file__).parent / "models"


def download_file(url, destination, description=""):
    print(f"\n📥 İndiriliyor: {description}")
    print(f"   URL: {url}")
    print(f"   Hedef: {destination}")

    try:
        def progress_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 / total_size)
                bar_length = 40
                filled = int(bar_length * percent / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(f'\r   [{bar}] {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)', end='')
            else:
                mb_downloaded = downloaded / (1024 * 1024)
                print(f'\r   İndirilen: {mb_downloaded:.1f} MB', end='')

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            block_size = 8192
            downloaded = 0
            with open(destination, 'wb') as f:
                while True:
                    block = response.read(block_size)
                    if not block:
                        break
                    f.write(block)
                    downloaded += len(block)
                    if total_size > 0:
                        percent = min(100, downloaded * 100 / total_size)
                        filled = int(40 * percent / 100)
                        bar = '█' * filled + '░' * (40 - filled)
                        mb_d = downloaded / (1024 * 1024)
                        mb_t = total_size / (1024 * 1024)
                        print(f'\r   [{bar}] {percent:.1f}% ({mb_d:.1f}/{mb_t:.1f} MB)', end='')
        print()
        print(f"   ✅ İndirme tamamlandı!")
        return True

    except Exception as e:
        print(f"\n   ❌ Hata: {e}")
        if os.path.exists(destination):
            os.remove(destination)
        return False


def verify_file(filepath, expected_size_mb=None):
    if not os.path.exists(filepath):
        return False
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if expected_size_mb and abs(file_size_mb - expected_size_mb) > 10:  # 10 MB tolerans
        print(f"   ⚠ Uyarı: Boyut uyuşmuyor ({file_size_mb:.1f} MB vs {expected_size_mb} MB beklenen)")
        return False
    return True


def download_all_models(skip_optional=False):
    print("=" * 70)
    print("  PDF AURA - AI MODEL İNDİRME ARACI")
    print("=" * 70)

    MODELS_DIR.mkdir(exist_ok=True)
    print(f"\n📁 Model klasörü: {MODELS_DIR}")

    success_count = 0
    fail_count = 0
    skip_count = 0

    for model_id, model_info in MODELS.items():
        print(f"\n{'─' * 70}")
        print(f"Model: {model_id}")
        print(f"Açıklama: {model_info['description']}")
        print(f"Boyut: ~{model_info['size_mb']} MB")

        if model_info.get('optional') and skip_optional:
            print("⏭ Opsiyonel model atlanıyor...")
            skip_count += 1
            continue

        destination = MODELS_DIR / model_info['filename']

        if destination.exists():
            if verify_file(destination, model_info['size_mb']):
                print(f"✅ Model zaten mevcut: {destination.name}")
                success_count += 1
                continue
            else:
                print(f"⚠ Mevcut model bozuk, yeniden indiriliyor...")
                destination.unlink()

        # URL varsa normal indir
        if model_info['url']:
            ok = download_file(model_info['url'], destination, model_info['description'])
            if ok and verify_file(destination, model_info['size_mb']):
                success_count += 1
            else:
                fail_count += 1
                print(f"   ❌ Model doğrulaması başarısız veya indirilemedi!")
        else:
            # URL yoksa atla
            print(f"   ⏭ Model URL'si yok, atlanıyor...")
            skip_count += 1

    print(f"\n{'=' * 70}")
    print(f"  ÖZET")
    print(f"{'=' * 70}")
    print(f"✅ Başarılı: {success_count}")
    print(f"❌ Başarısız: {fail_count}")
    if skip_count > 0:
        print(f"⏭ Atlanan: {skip_count}")
    print(f"{'=' * 70}\n")

    if fail_count == 0:
        print("🎉 Tüm modeller başarıyla indirildi!")
        print("\nŞimdi uygulamayı çalıştırabilirsiniz:")
        print("  python main.py")
    else:
        print("⚠ Bazı modeller indirilemedi.")
    return fail_count


def main():
    import argparse
    parser = argparse.ArgumentParser(description='PDF Aura AI modellerini indir')
    parser.add_argument('--skip-optional', action='store_true',
                        help='Opsiyonel modelleri atla')
    args = parser.parse_args()
    MODELS_DIR.mkdir(exist_ok=True)
    return download_all_models(skip_optional=args.skip_optional)


if __name__ == "__main__":
    sys.exit(main())