# -*- coding: utf-8 -*-
"""Dong goi Viet hoa cho launcher.

Cach dung:  python cong_cu/tao_goi.py <thu_muc_nguon> <ten_goi.zip>
  <thu_muc_nguon> chua cac file da Viet hoa, dung cau truc thu muc nhu trong thu muc game.
  Ket qua: zip co thu muc tep/..., in ra sha256 va kich_thuoc de dien vao danh_muc.json.
"""
import hashlib
import os
import sys
import zipfile


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    nguon, ra = sys.argv[1], sys.argv[2]
    so = 0
    with zipfile.ZipFile(ra, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for goc, _, tep in os.walk(nguon):
            for t in sorted(tep):
                p = os.path.join(goc, t)
                z.write(p, "tep/" + os.path.relpath(p, nguon).replace(os.sep, "/"))
                so += 1
    h = hashlib.sha256(open(ra, "rb").read()).hexdigest()
    print(f"Da dong goi {so} file -> {ra}")
    print(f'"sha256": "{h}",')
    print(f'"kich_thuoc": {os.path.getsize(ra)}')


if __name__ == "__main__":
    main()
