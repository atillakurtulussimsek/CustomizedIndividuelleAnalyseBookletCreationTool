# Analyse Booklet Engine — Customized Individuelle Analyse Booklet Creation Tool

> **TR** | YKS analiz raporlarını öğrenciye özel kapaklı, kitapçık baskısına hazır PDF'lere dönüştüren toplu işleme aracı.
>
> **EN** | Batch tool that turns YKS analysis reports into personalized, booklet-ready PDFs.

Sister project of [CustomizedPracticeExamBookletCreationTool](https://github.com/atillakurtulussimsek/CustomizedPracticeExamBookletCreationTool); same architecture, different PDF format.

---

## Nasıl Çalışır / How It Works

Her öğrenci PDF'i için:

1. **Tarama** — `input_pdfs/` içindeki PDF'ler bulunur (`front.pdf` ve `back.pdf` hariç).
2. **İsim çıkarma** — 1. sayfadaki **"Ad Soyad"** başlığının hemen altındaki hücre okunur (örn. `SİMAY DALGIÇ`).
3. **Ön kapak** — `front.pdf` içindeki `{{student.name}}` işaretçisinin üzerine öğrenci adı yazılır.
4. **Birleştirme** — `ön kapak + tüm analiz sayfaları (hiçbiri çıkarılmaz) + boş sayfa(lar) + arka kapak`.
5. **4'ün katı** — Toplam sayfa 4'ün katı değilse arka kapaktan **önce** boş sayfa eklenir.
6. **Çıktı** — `output_pdfs/<Öğrenci Adı>.pdf` (aynı isim varsa `(2)`, `(3)` eklenir).

```
[front.pdf] + [analysis p1..pN] + [blank × k] + [back.pdf]   →   total % 4 == 0
```

---

## Kurulum / Installation

```bash
git clone https://github.com/atillakurtulussimsek/CustomizedIndividuelleAnalyseBookletCreationTool.git
cd CustomizedIndividuelleAnalyseBookletCreationTool
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Türkçe karakterler için `fonts/` klasörüne `DejaVuSans.ttf` ve `DejaVuSans-Bold.ttf` koyun
(<https://dejavu-fonts.github.io/>).

---

## Kullanım / Usage

1. `input_pdfs/front.pdf` — ön kapak, metin katmanında `{{student.name}}` içermeli.
2. `input_pdfs/back.pdf` — arka kapak.
3. Öğrenci analiz PDF'lerini `input_pdfs/` içine koyun.

```bash
python -m src.cli run -c config.json            # tüm dosyalar
python -m src.cli run -c config.json -w 8       # 8 paralel işçi
python -m src.cli run -c config.json --dry-run  # sadece isimleri listele
python -m src.cli run -c config.json -s x.pdf   # tek dosya
python -m src.cli validate -c config.json       # girdileri doğrula
```

Tek tıkla: `./run.sh` (macOS/Linux) veya `run.bat` (Windows).

---

## Yapılandırma / Configuration (`config.json`)

| Alan | Açıklama |
|---|---|
| `front_template_filename` / `back_cover_filename` | Kapak dosya adları (`front.pdf`, `back.pdf`) |
| `name_extraction.page_index` | İsim tablosunun olduğu sayfa (0 = ilk sayfa) |
| `name_extraction.label_text` | İsim sütununun başlığı (`Ad Soyad`) |
| `name_extraction.row_gap_ratio` | Başlık ile değer satırı arasındaki azami mesafe (başlık yüksekliği cinsinden) |
| `template.marker_text` | Ön kapaktaki işaretçi (`{{student.name}}`) |
| `template.font_*` | İsim fontu, boyutu, rengi |
| `processing.max_workers` | Paralel işçi sayısı |
| `processing.booklet_page_multiple` | Sayfa katı (4) |
| `processing.delete_source_pdf` | Başarılı işlem sonrası kaynak PDF'i sil |

---

## Proje Yapısı / Project Structure

```
├── config.json
├── input_pdfs/            # front.pdf, back.pdf, öğrenci PDF'leri
├── output_pdfs/           # <Öğrenci Adı>.pdf
├── logs/                  # log + rapor CSV
├── fonts/                 # DejaVuSans*.ttf
├── src/
│   ├── cli.py                     # Click CLI
│   ├── core/
│   │   ├── template_processor.py  # {{student.name}} → isim
│   │   ├── assembler.py           # kapak + içerik + boş + arka kapak
│   │   ├── pipeline.py            # tek öğrenci akışı
│   │   └── engine.py              # paralel toplu işleme
│   ├── models/
│   │   ├── config.py              # Pydantic yapılandırma
│   │   └── records.py             # sonuç/öğrenci modelleri
│   └── utils/
│       ├── pdf_scanner.py         # "Ad Soyad" altından isim çıkarma
│       ├── font_manager.py
│       └── logging.py
└── tests/
    ├── fixtures.py                # analiz raporu benzeri test PDF'leri
    ├── generate_test_data.py      # python -m tests.generate_test_data
    └── test_engine.py
```

---

## Test

```bash
pip install pytest
python -m pytest -q
```

---

## Lisans / License

MIT
