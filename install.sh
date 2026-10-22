#!/data/data/com.termux/files/usr/bin/bash
# نصب V2Test در Termux
# اجرا (با VPN روشن):
#   curl -sL https://raw.githubusercontent.com/ali111e111n/myv2rayimporter/main/install.sh | bash
set -e

REPO="ali111e111n/myv2rayimporter"
KNIFE_URL="https://github.com/lilendian0x00/xray-knife/releases/latest/download/Xray-knife-android-arm64-v8a.zip"

echo "== V2Test installer =="

if [ "$(uname -m)" != "aarch64" ]; then
  echo "✗ این گوشی 64 بیتی (ARM64) نیست؛ xray-knife فقط برای ARM64 نسخه‌ی اندروید دارد."
  exit 1
fi

echo "→ نصب پیش‌نیازها..."
# ارتقای کامل لازم است؛ ارتقای ناقص باعث خطای «CANNOT LINK EXECUTABLE curl» می‌شود
yes | pkg upgrade -y -o Dpkg::Options::="--force-confold"
pkg install -y python curl unzip termux-api

echo "→ دریافت xray-knife (حدود ۲۵ مگابایت)..."
TMP="$(mktemp -d)"
curl -L --fail -o "$TMP/xk.zip" "$KNIFE_URL"
unzip -o -q "$TMP/xk.zip" xray-knife -d "$TMP"
install -m 755 "$TMP/xray-knife" "$PREFIX/bin/xray-knife"
rm -rf "$TMP"

echo "→ دریافت اسکریپت تست..."
curl -L --fail -o "$HOME/v2test.py" "https://raw.githubusercontent.com/$REPO/main/v2test.py" \
  || curl -L --fail -o "$HOME/v2test.py" "https://cdn.jsdelivr.net/gh/$REPO@main/v2test.py"

echo "→ ساخت دکمه‌ی ویجت..."
mkdir -p "$HOME/.shortcuts"
cat > "$HOME/.shortcuts/V2Test" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
python "$HOME/v2test.py"
echo
read -r -p "برای بستن Enter بزنید..." _
EOF
chmod +x "$HOME/.shortcuts/V2Test"

# دستور کوتاه برای اجرا از داخل Termux
grep -q "alias v2test=" "$HOME/.bashrc" 2>/dev/null || echo "alias v2test='python ~/v2test.py'" >> "$HOME/.bashrc"

echo
echo "✓ نصب کامل شد."
echo "  اجرا: ویجت Termux:Widget → V2Test   (یا در Termux بنویسید: v2test)"
