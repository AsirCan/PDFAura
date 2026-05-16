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
   - URL: https://huggingface.co/BritishWerewolf/U-2-Net/resolve/main/u2netp.onnx
   - Bu dosyayı `models/` klasörüne kaydedin

2. **u2net_document.onnx** (opsiyonel):
   - URL: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
   - Bu dosyayı `models/` klasörüne kaydedin

## Lisans

Bu modeller araştırma ve eğitim amaçlı kullanım için ücretsizdir.
Ticari kullanım için orijinal model sahiplerinin lisanslarını kontrol edin.

- U2-Net: https://github.com/xuebinqin/U-2-Net
