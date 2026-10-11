# AI Modelleri

Bu klasör, PDF Aura'nın belge köşe tespiti için kullandığı AI modellerini içerir.

## Modeller

### u2netp_document.onnx (Önerilen)
- **Boyut**: ~4.7 MB
- **Açıklama**: Hafif U2-Net-P modeli (ONNX formatında)
- **Kullanım**: Belge segmentasyonu ve köşe tespiti
- **Hız**: Çok hızlı (CPU'da bile)
- **Doğruluk**: İyi

### u2net_document.onnx (Opsiyonel)
- **Boyut**: ~168 MB
- **Açıklama**: Tam U2-Net modeli (ONNX formatında)
- **Kullanım**: Daha yüksek doğruluk gerektiren durumlar
- **Hız**: Orta (GPU önerilir)
- **Doğruluk**: Çok iyi

## Modelleri İndirme

Modelleri indirmek için proje kök dizininde şu komutu çalıştırın:

```bash
python download_models.py
```

Sadece hafif modeli indirmek için:

```bash
python download_models.py --skip-optional
```

## Manuel İndirme

Eğer otomatik indirme çalışmazsa, modelleri manuel olarak indirebilirsiniz:

1. **u2netp_document.onnx**:
   - URL: https://huggingface.co/chwshuang/Stable_diffusion_remove_background_model/resolve/b89fabdfd832c6adc357cfc7430e5eb60357a8ff/u2netp.onnx
   - SHA-256: `16fb536473a41b2e101bd3a6ff788f599b95e32ecbe20624c552b3d8ba91a11a` (4 571 475 bayt); uygulama yalnızca bu dosyayı kabul eder
   - Bu dosyayı `models/` klasörüne kaydedin

2. **u2net_document.onnx** (opsiyonel):
   - URL: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
   - Bu dosyayı `models/` klasörüne kaydedin

## Lisans

Bu modeller araştırma ve eğitim amaçlı kullanım için ücretsizdir.
Ticari kullanım için orijinal model sahiplerinin lisanslarını kontrol edin.

- U2-Net: https://github.com/xuebinqin/U-2-Net
