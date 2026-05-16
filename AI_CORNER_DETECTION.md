# 🤖 AI-Powered Document Corner Detection

PDF Aura'da belge köşe tespiti için **hibrit yapay zeka sistemi** kullanılmaktadır.

## 🎯 Nasıl Çalışır?

Sistem **3 farklı yaklaşımı** birleştirerek en iyi sonucu bulur:

### 1️⃣ ONNX Deep Learning Model (En Yüksek Öncelik)
- **Model**: U2-Net / U2-Net-P
- **Teknoloji**: Derin öğrenme tabanlı segmentasyon
- **Avantajlar**:
  - Karmaşık arka planları ayırt edebilir
  - Kötü ışıklandırmada bile çalışır
  - Gölgeli ve bulanık görüntülerde başarılı
  - Eğri ve katlanmış kağıtları tespit eder

### 2️⃣ ML-Enhanced Detection
- **GrabCut Segmentation**: Ön plan/arka plan ayrımı
- **Watershed Algorithm**: Bölge tabanlı segmentasyon
- **Multi-scale Edge Linking**: Çoklu ölçekli kenar bağlama

### 3️⃣ Classical Computer Vision
- **Canny Edge Detection**: Kenar tespiti
- **Adaptive Thresholding**: Adaptif eşikleme
- **Morphological Operations**: Morfolojik işlemler
- **Hough Line Detection**: Çizgi tespiti
- **Color-based Segmentation**: Renk tabanlı segmentasyon
- **Contour Hierarchy**: Kontur hiyerarşisi

## 📊 Kalite Değerlendirme Sistemi

Her tespit sonucu **4 kritere** göre puanlanır:

| Kriter | Ağırlık | Açıklama |
|--------|---------|----------|
| **Alan Skoru** | 25% | Belge boyutu görüntünün %15-95'i arasında mı? |
| **Kenar Skoru** | 35% | Köşeler görüntü kenarlarından uzak mı? |
| **En-Boy Oranı** | 20% | Belge oranı mantıklı mı? (1:1 ile 3:1 arası) |
| **Açı Skoru** | 20% | Köşeler 90 dereceye yakın mı? |

**En yüksek skoru alan tespit kazanır!**

## 🚀 Kurulum

### 1. Gerekli Kütüphaneleri Kurun
```bash
pip install -r requirements.txt
```

### 2. AI Modellerini İndirin
```bash
# Hafif model (~5 MB) - Önerilen
python download_models.py --skip-optional

# Veya tüm modeller (~180 MB)
python download_models.py
```

### 3. Uygulamayı Başlatın
```bash
python main.py
```

## 📁 Dosya Yapısı

```
PDFAura/
├── models/                          # AI modelleri
│   ├── u2netp_document.onnx        # Hafif model (4.7 MB)
│   ├── u2net_document.onnx         # Tam model (168 MB) - Opsiyonel
│   └── README.md
├── src/
│   └── core/
│       ├── document_scanner.py      # Ana hibrit sistem
│       ├── document_scanner_onnx.py # ONNX model entegrasyonu
│       └── document_scanner_ml.py   # ML-enhanced yöntemler
├── download_models.py               # Model indirme script'i
└── README.md
```

## 🔧 Teknik Detaylar

### U2-Net Mimarisi
```
Input Image (320x320)
    ↓
Encoder (6 stages)
    ↓
Nested U-blocks
    ↓
Decoder (6 stages)
    ↓
Segmentation Mask
    ↓
Corner Detection
```

### İşlem Akışı
```
1. Görüntü yükleme
2. Ön işleme (resize, normalize)
3. Paralel tespit:
   ├─ ONNX Model
   ├─ GrabCut
   ├─ Watershed
   ├─ Canny
   ├─ Adaptive
   ├─ Morphological
   ├─ Hough
   ├─ Color-based
   └─ Contour Hierarchy
4. Kalite skorlama
5. En iyi sonucu seç
6. Smart inset uygula
7. Köşeleri döndür
```

## 📈 Performans Karşılaştırması

| Yöntem | Hız (CPU) | Doğruluk | Karmaşık Arka Plan | Kötü Işık |
|--------|-----------|----------|-------------------|-----------|
| ONNX (u2netp) | ~200ms | ⭐⭐⭐⭐ | ✅ | ✅ |
| ONNX (u2net) | ~800ms | ⭐⭐⭐⭐⭐ | ✅ | ✅ |
| ML-Enhanced | ~150ms | ⭐⭐⭐⭐ | ✅ | ⚠️ |
| Classical CV | ~100ms | ⭐⭐⭐ | ⚠️ | ❌ |
| **Hibrit Sistem** | ~300ms | ⭐⭐⭐⭐⭐ | ✅ | ✅ |

## 🎨 Kullanım Örnekleri

### Kod İçinde Kullanım
```python
from src.core.document_scanner import detect_document_corners

# Otomatik köşe tespiti
corners = detect_document_corners("photo.jpg")
# [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]

# Köşeler: [top-left, top-right, bottom-right, bottom-left]
```

### GUI'de Kullanım
1. Scanner sekmesine gidin
2. "Fotoğraf Ekle" butonuna tıklayın
3. Köşeler otomatik tespit edilir
4. İsterseniz manuel düzeltme yapın
5. "Tara ve PDF Oluştur" butonuna tıklayın

## 🐛 Sorun Giderme

### Model bulunamadı
```
FileNotFoundError: ONNX modeli bulunamadı!
```
**Çözüm**: `python download_models.py` komutunu çalıştırın

### ONNX Runtime hatası
```
ImportError: onnxruntime kütüphanesi bulunamadı
```
**Çözüm**: `pip install onnxruntime`

### Köşeler yanlış tespit ediliyor
- Fotoğrafı daha iyi ışıklandırma ile çekin
- Belgenin tamamını çerçeveye alın
- Arka planı mümkünse düz ve tek renk yapın
- Manuel düzeltme yapın (köşeleri sürükleyin)

### Çok yavaş çalışıyor
- Hafif modeli kullanın (`--skip-optional`)
- Görüntü boyutunu küçültün
- GPU kullanın (CUDA destekli ONNX Runtime)

## 📚 Kaynaklar

- **U2-Net Paper**: [Going Deeper with Nested U-Structure](https://arxiv.org/abs/2005.09007)
- **ONNX Runtime**: https://onnxruntime.ai/
- **OpenCV**: https://opencv.org/
- **Model Weights**: https://github.com/xuebinqin/U-2-Net

## 📄 Lisans

- **PDF Aura**: Özel lisans
- **U2-Net Model**: Apache 2.0
- **ONNX Runtime**: MIT License

## 🙏 Teşekkürler

- Xuebin Qin ve ekibine U2-Net modeli için
- Microsoft'a ONNX Runtime için
- OpenCV topluluğuna

---

**Not**: Model olmadan da uygulama çalışır, ancak AI destekli tespit için model indirmeniz önerilir.
