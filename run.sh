#!/usr/bin/env bash
# ============================================================
#  Booklet Engine — Tek tıkla çalıştırma scripti
#  Sistem Python'unu kullanır; eksik bağımlılıkları otomatik kurar.
# ============================================================

# Scriptin bulunduğu dizine geç (her yerden çalışabilsin)
cd "$(dirname "$0")" || exit 1

echo "========================================"
echo "  Analyse Booklet Engine v1.0.0"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# --- Python 3.10+ yorumlayıcısı bul --------------------------
PY=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
    command -v "$candidate" &>/dev/null || continue
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "[HATA] Python 3.10 veya üstü bulunamadı."
    echo "       macOS : brew install python@3.12"
    echo "       Linux : sudo apt install python3.12"
    echo "       Diğer : https://www.python.org/downloads/"
    read -rp "Çıkmak için Enter'a basın..."
    exit 1
fi

echo "Python: $("$PY" --version 2>&1)  ($(command -v "$PY"))"

# --- Bağımlılıklar eksikse kur -------------------------------
if ! "$PY" -c "import click, pymupdf, pikepdf, reportlab, pydantic, rich" &>/dev/null; then
    echo ""
    echo "Bağımlılıklar eksik, kuruluyor (ilk çalıştırmada birkaç dakika sürebilir)..."
    # Önce normal dene; yeni Homebrew/Debian Python'ları (PEP 668)
    # sistem paketlerini korumak için ek bayrak ister.
    if ! "$PY" -m pip install --user -r requirements.txt 2>/dev/null; then
        if ! "$PY" -m pip install --user --break-system-packages -r requirements.txt; then
            echo ""
            echo "[HATA] Bağımlılıklar kurulamadı. İnternet bağlantınızı kontrol edin."
            read -rp "Çıkmak için Enter'a basın..."
            exit 1
        fi
    fi
    echo "✓ Bağımlılıklar kuruldu."
fi

echo ""

# --- Çalıştır -------------------------------------------------
"$PY" -m src.cli run --config config.json
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ İşlem başarıyla tamamlandı."
elif [ $EXIT_CODE -eq 2 ]; then
    echo "⚠ İşlem tamamlandı fakat bazı hatalar oluştu. Loglara bakın."
else
    echo "✗ İşlem başarısız oldu (çıkış kodu: $EXIT_CODE)."
fi

echo ""
read -rp "Çıkmak için Enter'a basın..."
exit $EXIT_CODE
