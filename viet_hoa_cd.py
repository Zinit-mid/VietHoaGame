# -*- coding: utf-8 -*-
"""Viet hoa Crimson Desert bang Claude: doc chu tieng Anh (nhom 0020) ngay trong thu muc game,
dich theo lo, luu bo nho dich (chay tiep duoc), xuat goi zip cho DMM.

- Giu nguyen tieng Anh: ten nhan vat, ten rieng (dia danh, phe phai), ten vat pham.
- Giu nguyen the: <br/>, {…}, [EMPTY]; kiem tra lai sau khi dich, sai thi dich lai / giu tieng Anh.
- Khoa Claude lay tu app Dich Game tren cung may (%APPDATA%\\DichGame\\khoa_api.txt).
"""
import concurrent.futures
import http.client
import json
import os
import re
import threading
import time
import zipfile

import crimson_desert as cd

DU_LIEU = os.path.join(os.environ.get("APPDATA") or os.path.dirname(os.path.abspath(__file__)), "VietHoaGame")
THU_MUC_CD = os.path.join(DU_LIEU, "crimson_desert")
FILE_BO_NHO = os.path.join(THU_MUC_CD, "bo_nho_dich.json")
DICH_GAME = os.path.join(os.environ.get("APPDATA") or "", "DichGame")
STEAM_APPID = "3321460"

DOT = {
    1: {"ten": "Đợt 1 – menu, nhiệm vụ, hội thoại cốt truyện, cắt cảnh",
        "file": ["ui", "localstringinfo", "quest", "questdialog", "sequencer", "narrationdialog", "talktree",
                 "stageclosedialog", "failmessage", "gameadvice", "interaction", "inventory", "equiptype",
                 "symboltext", "minigame", "platformservice", "uisocialaction", "lookat", "board", "bank"]},
    2: {"ten": "Đợt 2 – lời thoại chiến đấu / đi đường, mô tả vật phẩm, phe phái, kỹ năng, sự kiện",
        "file": ["aidialog", "item", "multichange", "gimmick", "character", "npc", "faction", "patterndescription",
                 "managementbuff", "managementneedssynergy", "globalgameevent", "entitlement", "housingobject",
                 "sublevel", "house", "housingroom", "housingobjectgroup", "socket"],
        # cac file nay lan ten va mo ta: chi dich CAU (mo ta), giu nguyen ten / nhan
        "chi_cau": ["item", "multichange", "gimmick", "character", "npc", "faction", "housingobject"]},
}
# file chi chua ten -> lam bang ten rieng (giu nguyen, khong dich)
FILE_TEN = ["npcname", "character", "region", "faction", "factionoperationgroup", "item", "itemgroup",
            "housingobject", "dyecolorgroup", "personality"]

MO_HINH = "claude-haiku-5-5"
GIA_MAC_DINH = [0.10, 0.50]   # USD / 1 trieu token (vao, ra) – lay theo cau hinh Dich Game neu co
KY_TU_MOI_LO = 6000
CAU_MOI_LO = 40
SO_LUONG = 4

HUONG_DAN = """Bạn là dịch giả chuyên Việt hóa game. Game: Crimson Desert (nhập vai thế giới mở, trung cổ kỳ ảo; \
nhân vật chính Kliff, thủ lĩnh nhóm lính đánh thuê Greymanes; lục địa Pywel).
Bạn nhận một mảng JSON các chuỗi tiếng Anh lấy từ file chữ của game và trả về mảng JSON các bản dịch tiếng Việt.

Quy tắc bắt buộc:
- CHỈ trả về một mảng JSON hợp lệ, CÙNG SỐ PHẦN TỬ, CÙNG THỨ TỰ. Không giải thích, không ```.
- GIỮ NGUYÊN tiếng Anh: tên nhân vật, tên người, địa danh, phe phái, tổ chức, tên vật phẩm, tên trang bị, \
tên kỹ năng riêng, và mọi từ trong danh sách "Giữ nguyên" nếu có.
- Giữ NGUYÊN từng ký tự các thẻ: <br/>, <...>, {...} (VD {Key:Key_Jump}, {Param1}), [EMPTY]. Không dịch, không thêm, không bớt thẻ.
- Giữ nguyên số, ký hiệu, khoảng trắng đầu/cuối và cách xuống dòng.
- Văn phong tự nhiên như phụ đề phim kỳ ảo/cổ trang. Xưng hô hợp ngữ cảnh \
(ta – ngươi, tôi – ngài, anh – em, ta – các ngươi...).
- Menu, nút bấm, tiêu đề nhiệm vụ: ngắn gọn, rõ nghĩa như game Việt hóa chính thức.
- Chuỗi chỉ gồm tên riêng hoặc không có gì để dịch: trả lại y nguyên."""

THE = re.compile(r"<[^<>]*>|\{[^{}]*\}|\[EMPTY\]")


def khong_can_dich(s):
    t = THE.sub("", s).strip()
    return not t or not re.search(r"[A-Za-z]{2,}", t)


def la_cau(s):
    """Chuoi la cau / doan van (mo ta) chu khong phai ten hay nhan ngan."""
    t = THE.sub(" ", s).strip()
    if "<br/>" in s or len(t) >= 70:
        return True
    return len(t.split()) >= 4 and (t.endswith((".", "!", "?", "…", '"')) or ". " in t)


def the_cua(s):
    return sorted(THE.findall(s))


# ================================================================ bang ten rieng

class BangTen:
    def __init__(self, ten):
        self.ten = {t for t in ten if 2 <= len(t) <= 40}
        self.dai = max((len(t.split()) for t in self.ten), default=1)

    @staticmethod
    def tao(nhom):
        ten = set()
        for f in FILE_TEN:
            for _, _, v in nhom.get(f, {}).get("ds", []):
                v = THE.sub("", v).strip()
                if (v and len(v) <= 40 and "\n" not in v and not v.endswith((".", "!", "?", ":"))
                        and v[0].isupper() and len(v.split()) <= 5):
                    ten.add(v)
        # bo cac tu thong dung de khong chan dich nham
        thuong = {"Talk", "Map", "Quest", "Quests", "Inventory", "Continue", "Settings", "Options", "Yes", "No",
                  "Gold", "Silver", "Food", "Water", "Wood", "Stone", "Iron", "Horse", "Sword", "Shield", "Bow",
                  "Help", "Back", "Close", "Cancel", "Confirm", "Accept", "Reward", "Rewards", "Level", "None"}
        return BangTen(ten - thuong)

    def trong(self, van_ban):
        """Cac ten rieng xuat hien trong van ban (cum chu viet hoa)."""
        kq = set()
        tu = re.findall(r"[A-Za-z][A-Za-z'’-]*", van_ban)
        for i in range(len(tu)):
            if not tu[i][0].isupper():
                continue
            for n in range(min(self.dai, len(tu) - i), 0, -1):
                cum = " ".join(tu[i:i + n])
                if cum in self.ten:
                    kq.add(cum)
                    break
        return kq

    def la_ten(self, s):
        return s.strip() in self.ten


# ================================================================ Claude

class LoiDung(Exception):
    """Loi khong the tiep tuc (sai khoa, het tien...)."""


class Claude:
    MAY_CHU = "api.anthropic.com"

    def __init__(self, khoa, mo_hinh=MO_HINH):
        self.khoa = khoa
        self.mo_hinh = mo_hinh
        self.kieu = None
        self.rieng = threading.local()

    def _ket_noi(self, moi=False):
        c = getattr(self.rieng, "c", None)
        if moi or c is None:
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass
            c = http.client.HTTPSConnection(self.MAY_CHU, timeout=180)
            self.rieng.c = c
        return c

    def goi(self, noi_dung, max_tokens):
        body = json.dumps({"model": self.mo_hinh, "max_tokens": max_tokens, "system": HUONG_DAN,
                           "messages": [{"role": "user", "content": noi_dung}]}).encode("utf-8")
        for lan in range(6):
            for kieu in ([self.kieu] if self.kieu else ["x-api-key", "bearer"]):
                dau = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
                if kieu == "bearer":
                    dau["authorization"] = "Bearer " + self.khoa
                else:
                    dau["x-api-key"] = self.khoa
                try:
                    c = self._ket_noi(moi=lan > 0)
                    c.request("POST", "/v1/messages", body=body, headers=dau)
                    r = c.getresponse()
                    du_lieu = r.read().decode("utf-8", "ignore")
                except (http.client.HTTPException, OSError):
                    time.sleep(2 + lan * 3)
                    break
                if r.status in (401, 403):
                    continue
                if r.status in (429, 500, 502, 503, 529):
                    time.sleep(5 + lan * 10)
                    break
                if r.status >= 400:
                    try:
                        tb = json.loads(du_lieu)["error"]["message"]
                    except Exception:
                        tb = du_lieu[:200]
                    if "credit" in tb.lower() or "billing" in tb.lower():
                        raise LoiDung("tài khoản Claude hết tiền: " + tb)
                    raise RuntimeError(f"HTTP {r.status}: {tb}")
                self.kieu = kieu
                d = json.loads(du_lieu)
                chu = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
                u = d.get("usage", {})
                return chu, u.get("input_tokens", 0), u.get("output_tokens", 0)
            else:
                raise LoiDung("mã Claude không hợp lệ (HTTP 401/403) – kiểm tra lại mã trong app Dịch Game")
        raise RuntimeError("Claude bận hoặc mất mạng, đã thử lại nhiều lần")


def doc_khoa_claude():
    p = os.path.join(DICH_GAME, "khoa_api.txt")
    try:
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def doc_gia():
    try:
        with open(os.path.join(DICH_GAME, "cau_hinh.json"), encoding="utf-8") as f:
            c = json.load(f)
        g = c.get("gia_usd_moi_trieu_token")
        if isinstance(g, list) and len(g) == 2:
            return [float(g[0]), float(g[1])], c.get("mo_hinh") or MO_HINH
    except Exception:
        pass
    return list(GIA_MAC_DINH), MO_HINH


def tach_json(chu, so):
    chu = chu.strip()
    if chu.startswith("```"):
        chu = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", chu)
    i, j = chu.find("["), chu.rfind("]")
    if i < 0 or j < i:
        raise ValueError("không thấy mảng JSON")
    ds = json.loads(chu[i:j + 1])
    if not isinstance(ds, list) or len(ds) != so or not all(isinstance(x, str) for x in ds):
        raise ValueError("sai số phần tử")
    return ds


# ================================================================ cong viec

class ViecDich:
    """Mot lan Viet hoa: doc game -> lap danh sach cau can dich -> dich -> xuat goi."""

    def __init__(self, thu_muc_game, dot=1):
        self.thu_muc_game = thu_muc_game
        self.dot = dot
        self.nhom = None
        self.bang_ten = None
        self.bo_nho = {}
        self.khoa = threading.Lock()
        self.dung = threading.Event()
        self.da_doi = 0
        self.tien = 0.0
        self.loi = 0

    # ---------------------------------------------------------- chuan bi
    def nap(self, bao=lambda s: None):
        thu_muc = os.path.join(self.thu_muc_game, "0020")
        if not os.path.isfile(os.path.join(thu_muc, "0.pamt")):
            raise LoiDung("không thấy thư mục chữ tiếng Anh (0020) trong thư mục game")
        bao("Đang đọc chữ tiếng Anh của game...")
        self.nhom = cd.doc_nhom(thu_muc)
        self.bang_ten = BangTen.tao(self.nhom)
        try:
            with open(FILE_BO_NHO, encoding="utf-8") as f:
                self.bo_nho = json.load(f)
        except Exception:
            self.bo_nho = {}
        return self

    def luu(self):
        os.makedirs(THU_MUC_CD, exist_ok=True)
        with self.khoa:
            du_lieu = json.dumps(self.bo_nho, ensure_ascii=False)
        tam = FILE_BO_NHO + ".tmp"
        with open(tam, "w", encoding="utf-8") as f:
            f.write(du_lieu)
        os.replace(tam, FILE_BO_NHO)

    def nen_dich(self, f, v, dot=None):
        """Chuoi v trong file f co thuoc dien dich khong (dung luat cua dot chua file f)."""
        if khong_can_dich(v) or self.bang_ten.la_ten(v):
            return False
        d = dot or next((k for k, x in DOT.items() if f in x["file"]), None)
        if d is None:
            return False
        if f in DOT[d].get("chi_cau", []) and not la_cau(v):
            return False
        return True

    def _chuoi_cua_dot(self):
        for f in DOT[self.dot]["file"]:
            for _, _, v in self.nhom.get(f, {}).get("ds", []):
                if self.nen_dich(f, v, self.dot):
                    yield v

    def cau_can_dich(self):
        """Cac chuoi tieng Anh (khong trung) cua dot nay chua co trong bo nho."""
        ds, da = [], set()
        for v in self._chuoi_cua_dot():
            if v in da or v in self.bo_nho:
                continue
            da.add(v)
            ds.append(v)
        return ds

    def thong_ke(self):
        tat_ca = set(self._chuoi_cua_dot())
        con = self.cau_can_dich()
        return {"tong": len(tat_ca), "da_dich": sum(1 for v in tat_ca if v in self.bo_nho),
                "con": len(con), "ky_tu_con": sum(len(v) for v in con)}

    @staticmethod
    def uoc_tinh_usd(ky_tu, gia):
        vao = ky_tu / 3.6 * 1.35 + 900 * (ky_tu / KY_TU_MOI_LO + 1)   # chu + huong dan moi lo
        ra = ky_tu / 3.6 * 1.9
        return vao * gia[0] / 1e6 + ra * gia[1] / 1e6

    # ---------------------------------------------------------- dich
    def _chia_lo(self, ds):
        lo, ky = [], 0
        for v in ds:
            if lo and (len(lo) >= CAU_MOI_LO or ky + len(v) > KY_TU_MOI_LO):
                yield lo
                lo, ky = [], 0
            lo.append(v)
            ky += len(v)
        if lo:
            yield lo

    def _dich_lo(self, claude, lo, gia):
        ten = set()
        for v in lo:
            ten |= self.bang_ten.trong(v)
        phan = []
        if ten:
            phan.append("Giữ nguyên (không dịch): " + ", ".join(sorted(ten)[:150]))
        phan.append(json.dumps(lo, ensure_ascii=False))
        noi_dung = "\n\n".join(phan)
        max_tok = min(16000, int(sum(len(v) for v in lo) / 1.2) + 800)
        tien = 0.0
        for lan in range(2):
            chu, vao, ra = claude.goi(noi_dung, max_tok)
            tien += vao * gia[0] / 1e6 + ra * gia[1] / 1e6
            try:
                kq = tach_json(chu, len(lo))
                break
            except ValueError:
                kq = None
        if kq is None:
            if len(lo) > 1:   # chia doi roi thu lai
                giua = len(lo) // 2
                a, ta = self._dich_lo(claude, lo[:giua], gia)
                b, tb = self._dich_lo(claude, lo[giua:], gia)
                return a + b, tien + ta + tb
            return [None], tien
        ra_ds = []
        for en, vi in zip(lo, kq):
            ok = vi.strip() and the_cua(en) == the_cua(vi)
            ra_ds.append(vi if ok else None)
        return ra_ds, tien

    def chay(self, khoa_claude, gioi_han_usd, bao, tien_do):
        gia, mo_hinh = doc_gia()
        claude = Claude(khoa_claude, mo_hinh)
        ds = self.cau_can_dich()
        tong = len(ds)
        if not tong:
            bao("Đợt này đã dịch xong hết.")
            return True
        self.dung.clear()
        self.tien = 0.0
        lo_list = list(self._chia_lo(ds))
        xong = 0
        lan_luu = time.time()
        bao(f"Bắt đầu dịch {tong} câu ({len(lo_list)} lô)...")
        with concurrent.futures.ThreadPoolExecutor(SO_LUONG) as ex:
            dang = {}
            it = iter(lo_list)

            def nop():
                if self.dung.is_set() or self.tien >= gioi_han_usd:
                    return False
                lo = next(it, None)
                if lo is None:
                    return False
                dang[ex.submit(self._dich_lo, claude, lo, gia)] = lo
                return True

            for _ in range(SO_LUONG):
                nop()
            while dang:
                xong_f, _ = concurrent.futures.wait(dang, return_when=concurrent.futures.FIRST_COMPLETED)
                for f in xong_f:
                    lo = dang.pop(f)
                    try:
                        kq, tien = f.result()
                    except LoiDung as e:
                        self.dung.set()
                        bao(f"Dừng: {e}")
                        continue
                    except Exception as e:
                        self.loi += 1
                        bao(f"Lỗi một lô ({e}) – bỏ qua, lần sau chạy tiếp sẽ dịch lại")
                        continue
                    with self.khoa:
                        self.tien += tien
                        for en, vi in zip(lo, kq):
                            if vi is not None:
                                self.bo_nho[en] = vi
                                self.da_doi += 1
                            else:
                                self.loi += 1
                    xong += len(lo)
                    tien_do(xong, tong, self.tien)
                    if time.time() - lan_luu > 20:
                        self.luu()
                        lan_luu = time.time()
                    nop()
        self.luu()
        if self.tien >= gioi_han_usd:
            bao(f"Đã chạm giới hạn {gioi_han_usd:.2f} USD – bấm Dịch lần nữa để chạy tiếp.")
            return False
        if self.dung.is_set():
            return False
        return not self.cau_can_dich()

    # ---------------------------------------------------------- xuat goi DMM
    def xuat_goi(self, duong_dan_zip):
        tam = os.path.join(THU_MUC_CD, "goi_tam")
        import shutil
        shutil.rmtree(tam, ignore_errors=True)
        ban_dich = {}
        for f in sorted({x for d in DOT.values() for x in d["file"]}):
            g = self.nhom.get(f)
            if not g:
                continue
            m = {k: self.bo_nho[v] for _, k, v in g["ds"]
                 if v in self.bo_nho and self.bo_nho[v] != v and self.nen_dich(f, v)}
            if m:
                ban_dich[f] = m
        thong_ke = cd.dong_goi(self.nhom, ban_dich, tam, "eng")
        ten_mod = "VietHoa_CrimsonDesert"
        os.makedirs(os.path.dirname(os.path.abspath(duong_dan_zip)), exist_ok=True)
        with zipfile.ZipFile(duong_dan_zip, "w", zipfile.ZIP_DEFLATED) as z:
            goc = os.path.join(tam, "gamedata")
            for thu_muc, _, tep in os.walk(goc):
                for t in tep:
                    p = os.path.join(thu_muc, t)
                    z.write(p, f"{ten_mod}/0020/" + os.path.relpath(p, tam).replace(os.sep, "/"))
        shutil.rmtree(tam, ignore_errors=True)
        return thong_ke
