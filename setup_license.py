from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

base = Path(__file__).resolve().parent
key_path = base / 'PRIVATE_LICENSE_KEY.pem'
if key_path.exists():
    raise SystemExit('PRIVATE_LICENSE_KEY.pem đã tồn tại; không ghi đè khóa cũ.')
private = Ed25519PrivateKey.generate()
key_path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
public_hex = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
app_path = base / 'Autoskill_Hominhtuan95.py'
source = app_path.read_text(encoding='utf-8')
if 'REPLACE_WITH_PUBLIC_KEY' not in source:
    raise SystemExit('Không tìm thấy vị trí thay khóa công khai.')
app_path.write_text(source.replace('REPLACE_WITH_PUBLIC_KEY', public_hex), encoding='utf-8')
print('Đã tạo khóa riêng và cài khóa công khai vào mã nguồn.')
print('TUYỆT ĐỐI KHÔNG tải PRIVATE_LICENSE_KEY.pem lên GitHub.')
